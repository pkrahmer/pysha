#!/usr/bin/env python3

from gi.repository import GLib
import platform
from heatpump import Heatpump
import logging
import sys
import os
from topics import *

sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))
from vedbus import VeDbusService


class DbusAquareaService(object):

    def __init__(self, servicename, deviceinstance, productname='Aquarea Heatpump', connection='RS485'):
        self._dbusservice = VeDbusService(servicename)
        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion',
                                   'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 4711)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

        for topic in topics:
            self._dbusservice.add_path(path=F"/Topic/{topic.name}", value=None,
                                       description=topic.help,
                                       writeable=topic.writable,
                                       onchangecallback=self.on_value_changed if topic.writable else None,
                                       gettextcallback=self.on_get_text)

        self.heatpump = Heatpump("/dev/ttyUSB0", 10, 2, self.on_topic_received, None)

        GLib.timeout_add(50, self.heatpump.loop)

    def on_topic_received(self, topic: Topic) -> bool:
        if not topic.delegated:
            logging.info(f"topic: {topic}")
            self._dbusservice[F"/Topic/{topic.name}"] = topic.value
            return True

    def on_value_changed(self, path: str, value):
        if path.lower().startswith("/topic/"):
            logging.info(F"setting {path[7:]} to {value}")
            self.heatpump.command(path[7:], value)
            return True  # accept the change

        return False

    def on_get_text(self, path: str, value):
        for topic in topics:
            if F"/topic/{topic.name.lower()}" == path.lower():
                return topic.description

        return value




def main():
    logging.basicConfig(level=logging.INFO)

    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)

    pvac_output = DbusAquareaService(
        servicename='com.victronenergy.pysha.ttyO1',
        deviceinstance=0)

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
