#!/usr/bin/env python3

from gi.repository import GLib
from heatpump import Heatpump
from topics import *
import paho.mqtt.client as paho

class Main(object):

    def __init__(self):
        self.client1 = paho.Client("control1")
        self.client1.connect("localhost", 1883)

        for topic in topics:
            self.client1.subscribe(
                topic=F"Pysha/Set/{topic.name}")

        self.client1.loop_start()

        self.client1.on_message = self.on_message

        self.heatpump = Heatpump(
            device="/dev/ttyUSB0",
            poll_interval=10,
            optional_pcb_poll_interval=2,
            on_topic_received=self.on_topic_received,
            on_topic_data=None)

        GLib.timeout_add(50, self.heatpump.loop)

    def on_topic_received(self, topic: Topic) -> bool:
        if not topic.delegated:
            rc, mid = self.client1.publish(
                topic=F"Pysha/{topic.name}",
                payload=topic.to_json())

            logging.info(f"topic: {topic} {mid} {rc}")

            return rc == 0

    def on_message(self, client, userdata, message: paho.MQTTMessage):
        if not message.retain and message.payload is not None and message.topic.startswith("Pysha/Set/"):
            try:
                value = message.payload.decode('utf-8')
                self.heatpump.command(message.topic[10:], value)
                logging.info(F"Setting {message.topic[10:]} to '{value[:20]}'")
            except ValueError as e:
                logging.warning(e)


    def on_value_changed(self, path: str, value):
        #if path.lower().startswith("/topic/"):
        #    logging.info(F"setting {path[7:]} to {value}")
        #    self.heatpump.command(path[7:], value)
        #    return True  # accept the change

        return False




def main():
    logging.basicConfig(level=logging.INFO)

    Main()

    logging.info('Connected')
    mainloop = GLib.MainLoop()
    mainloop.run()



if __name__ == "__main__":
    main()
