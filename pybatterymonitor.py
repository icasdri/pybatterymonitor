#!/usr/bin/env python3

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import dbus
import dbus.service
import sys
import logging
from requests.sessions import session

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.DEBUG)
log.addHandler(_handler)

MY_PATH = "/org/icasdri/batterymonitor"
MY_IFACE = "org.icasdri.batterymonitor"

UPOWER_NAME = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower"
UPOWER_IFACE = UPOWER_NAME
DEV_IFACE = "org.freedesktop.UPower.Device"

LOGIND_MANAGER_IFACE = "org.freedesktop.login1.Manager"
LOGIND_SESSION_IFACE = "org.freedesktop.login1.Session"

DEVICE_TYPES = {"Unknown": 0, "Line Power": 1, "Battery": 2}

class BatteryMonitor(dbus.service.Object):
    def __init__(self, system_bus, session_bus):
        self.system_bus = system_bus
        self.session_bus = session_bus
        bus_name = dbus.service.BusName(MY_IFACE, bus=self.session_bus)
        dbus.service.Object.__init__(self, bus_name, MY_PATH)

        self.upower = dbus.Interface(
            self.system_bus.get_object(UPOWER_NAME, UPOWER_PATH),
            UPOWER_IFACE)

        self.upower.connect_to_signal("PropertiesChanged",
                                      self.handle_upower_signal,
                                      dbus_interface=dbus.PROPERTIES_IFACE)
        self.system_bus.add_signal_receiver(self.handle_prepare_for_sleep_signal,
                                            signal_name="PrepareForSleep",
                                            dbus_interface=LOGIND_MANAGER_IFACE)
        self.system_bus.add_signal_receiver(self.handle_unlock_signal,
                                            signal_name="Unlock",
                                            dbus_interface=LOGIND_SESSION_IFACE)

        self.battery = None
        self.init_battery()

    def init_battery(self):
        for dev_path in self.upower.EnumerateDevices():
            dev_obj = self.system_bus.get_object(UPOWER_NAME, dev_path)
            dev_props = dbus.Interface(dev_obj, dbus.PROPERTIES_IFACE)
            if dev_props.Get(DEV_IFACE, "Type") == DEVICE_TYPES["Battery"] and \
                            dev_props.Get(DEV_IFACE, "PowerSupply") == True:
                self.battery = dev_props
                log.info("Found battery {} {}".format(dev_props.Get(DEV_IFACE, "Vendor"), dev_props.Get(DEV_IFACE, "Model")))
                self.battery.connect_to_signal("PropertiesChanged", self.handle_battery_signal)
                break
        else:
            log.warning("No Battery device found!")

    def handle_battery_signal(self, interface, data, signature):
        if "Percentage" in data:
            log.info("Battery now at {} percent".format(data["Percentage"]))

    def handle_upower_signal(self, interface, data, signature):
        if "OnBattery" in data:
            if data["OnBattery"]:
                log.info("Now running on Battery")
            else:
                log.info("Now running on Line Power")

    def handle_unlock_signal(self):
        log.info("A session has been unlocked")

    def handle_prepare_for_sleep_signal(self, indicator):
        if indicator == 0:
            log.info("System is going for sleep!")
        else:
            log.info("System has exited sleep")

    def handle_signal(self, *posargs, **kwargs):
        #print("Positional Arguments")
        for i, p in enumerate(posargs):
            print("{}: {}".format(i, p))
        #print("Keyword Arguments")
        for k, a in kwargs.items():
            print("{}: {}".format(k, a))
        print()

    def handle_device_added_signal(self):
        pass


if __name__ == "__main__":
    from dbus.mainloop.glib import DBusGMainLoop
    from gobject import MainLoop
    DBusGMainLoop(set_as_default=True)
    BatteryMonitor(dbus.SystemBus(), dbus.SessionBus())
    MainLoop().run()

