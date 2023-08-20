import traceback
from datetime import datetime, timedelta

from topics import *
from queue import Queue
import serial
import logging

minimum_poll_interval = 2


class Heatpump:
    def __init__(self, device: str, poll_interval: int, optional_pcb_poll_interval: int,
                 on_topic_received: any, on_topic_data: any):

        self.pollQuery = [0x71, 0x6c, 0x01, 0x10] + [0x00] * 106
        self.sendQuery = [0xf1, 0x6c, 0x01, 0x10] + [0x00] * 106
        self.optionalPCBQuery = [0xF1, 0x11, 0x01, 0x50, 0x00, 0x00, 0x40, 0xFF, 0xFF, 0xE5,
                                 0xFF, 0xFF, 0x00, 0xFF, 0xEB, 0xFF, 0xFF, 0x00, 0x00]

        self.device = device
        self.onTopicReceived = on_topic_received
        self.onTopicData = on_topic_data
        self.commandQueue = Queue()
        self.pollInterval = None if poll_interval <= 0 else minimum_poll_interval \
            if poll_interval < minimum_poll_interval else poll_interval

        self.optionalPollInterval = None if optional_pcb_poll_interval <= 0 else minimum_poll_interval \
            if optional_pcb_poll_interval < minimum_poll_interval else optional_pcb_poll_interval

        self.serial = serial.Serial(self.device,
                                    baudrate=9600,
                                    parity=serial.PARITY_EVEN,
                                    stopbits=serial.STOPBITS_ONE,
                                    timeout=0.2)

        if self.pollInterval:
            logging.info(F"heatpump: connected to {self.device} with 9600-8-E-1, poll interval {self.pollInterval}s")
            self.nextPoll = datetime.now() + timedelta(seconds=2)
        else:
            logging.info(F"heatpump: connected to {self.device} with 9600-8-E-1, no polling")
            self.nextPoll = datetime.max

        if self.optionalPollInterval:
            logging.info(F"heatpump: simulating optional pcb with poll interval {self.optionalPollInterval}s")
            self.nextOptionalPoll = datetime.now() + timedelta(seconds=0)
        else:
            self.nextOptionalPoll = datetime.max

        self.nextAllowedSend = datetime.now() + timedelta(seconds=minimum_poll_interval)

    def on_receive(self, buffer: []):
        if len(buffer) == 20:
            # optional pcb response to heatpump should contain the data from heatpump on byte 4 and 5
            self.optionalPCBQuery[4] = buffer[4]
            self.optionalPCBQuery[5] = buffer[5]
            buffer = self.optionalPCBQuery + [checksum(self.optionalPCBQuery)]

        if decode_and_update_topic(buffer):
            if self.onTopicData is not None:
                self.onTopicData("optional" if len(buffer) == 20 else "main", buffer)

            for topic in topics:
                if self.onTopicReceived is not None:
                    if self.onTopicReceived(topic):
                        topic.delegated = True

    def shutdown(self):
        logging.info("heatpump: disconnecting")
        self.serial.close()

    def command(self, name: str, param: any):
        topic = find_topic(name)
        if topic is None or not topic.writable:
            raise ValueError(F"Command {name} does not exist.")
        if not topic.accepts(param):
            raise ValueError(F"Command {name} does not accept value '{param}'.")
        self.commandQueue.put((topic, topic.parse(param)))

    # def optional_command(self, name: str, param: int):
    #    if self.optionalCommand.set(name, param):
    #        self.nextOptionalPoll = datetime.now() + timedelta(seconds=minimum_poll_interval)
    #        return True
    #    else:
    #        return False

    def loop(self) -> []:
        buffer = []

        if self.serial.in_waiting > 0:

            while True:
                single_or_no_byte = self.serial.read(1)
                if len(single_or_no_byte) > 0:
                    buffer += single_or_no_byte
                else:
                    break

            if len(buffer) > 0:
                # try:
                self.on_receive(buffer)
                # except Exception as err:
                #    self.nextPoll = datetime.now() + timedelta(seconds=minimum_poll_interval)
                #    logging.error(F"Unknown error while processing received data: {err}")

        if self.nextAllowedSend < datetime.now():

            if not self.commandQueue.empty():
                try:
                    (topic, param) = self.commandQueue.get()

                    query = self.optionalPCBQuery if topic.optional else self.sendQuery.copy()
                    (idx, byte) = topic.encode(query, param)
                    query[idx] = byte

                    if query is not None:
                        self.nextAllowedSend = datetime.now() + timedelta(seconds=minimum_poll_interval)
                        logging.info(F"raw command: {topic} {param} -> {query}")
                        self.serial.write(query + [checksum(query)])

                    else:
                        logging.warning(F"Unknown command or invalid parameter '{topic}({param})'")
                except Exception as err:
                    logging.error(F"Unknown error while sending command: {err}")

            elif self.nextPoll < datetime.now():
                try:
                    logging.debug(F"Polling for new data {self.pollQuery}")
                    self.nextPoll = datetime.now() + timedelta(seconds=self.pollInterval)
                    self.nextAllowedSend = datetime.now() + timedelta(seconds=minimum_poll_interval)
                    self.serial.write(self.pollQuery + [checksum(self.pollQuery)])
                except Exception as err:
                    logging.error(F"Unknown error while polling: {err}")

            elif self.nextOptionalPoll < datetime.now():
                try:
                    logging.debug(F"Polling for new optional data {self.optionalPCBQuery}")
                    self.nextOptionalPoll = datetime.now() + timedelta(seconds=self.optionalPollInterval)
                    self.nextAllowedSend = datetime.now() + timedelta(seconds=minimum_poll_interval)
                    self.serial.write(self.optionalPCBQuery + [checksum(self.optionalPCBQuery)])
                except Exception as err:
                    logging.error(F"Unknown error while polling optional data: {err}")

        return True

