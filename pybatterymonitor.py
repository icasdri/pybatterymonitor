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

DEVICE_TYPES = {"Unknown": 0, "Line Power": 1, "Battery": 2}
BATTERY_STATES = {0: "Unknown",
                  1: "Charging",
                  2: "Discharging",
                  3: "Empty",
                  4: "Fully Charged",
                  5: "Pending Charge",
                  6: "Pending Discharge"}

class BatteryMonitor(dbus.service.Object):
    def __init__(self, system_bus, session_bus, lower_bound=40, upper_bound=80, warn_step=5):
        self.lower_bound = 40
        self.upper_bound = 80
        self.warn_step = 5

        self.system_bus = system_bus
        self.session_bus = session_bus
        bus_name = dbus.service.BusName(MY_IFACE, bus=self.session_bus)
        dbus.service.Object.__init__(self, bus_name, MY_PATH)

        self.battery = None
        self.discharging = None
        self.next_warning = None
        self.warning_generator = None
        self.init_battery()

    def init_battery(self):
        upower = dbus.Interface(self.system_bus.get_object(UPOWER_NAME, UPOWER_PATH), UPOWER_IFACE)
        for dev_path in upower.EnumerateDevices():
            dev_obj = self.system_bus.get_object(UPOWER_NAME, dev_path)
            dev_props = dbus.Interface(dev_obj, dbus.PROPERTIES_IFACE)
            if dev_props.Get(DEV_IFACE, "Type") == DEVICE_TYPES["Battery"] and \
                            dev_props.Get(DEV_IFACE, "PowerSupply") == True:
                self.battery = dev_props
                log.info("Found battery {} {}".format(dev_props.Get(DEV_IFACE, "Vendor"), dev_props.Get(DEV_IFACE, "Model")))
                self.update_percentage(self.battery.Get(DEV_IFACE, "Percentage"))
                self.update_state(self.battery.Get(DEV_IFACE, "State"))
                self.update_warnings()
                self.battery.connect_to_signal("PropertiesChanged", self.handle_battery_signal)
                break
        else:
            log.warning("No Battery device found!")

    def handle_battery_signal(self, interface, data, signature):
        if "Percentage" in data:
            self.update_percentage(data["Percentage"])
        if "State" in data:
            self.update_state(data["State"])

    def new_warning_generator(self):
        if self.discharging:
            for i in range(self.lower_bound, 0, -self.warn_step):
                yield (True, i)
            yield (True, 0)
        else:
            for i in range(self.upper_bound, 100, self.warn_step):
                yield (False, i)
            yield (False, 100)

    def warn(self, percentage):
        if self.discharging:
            warn_string = "Battery is now at {} percent. Consider ending discharge."
        else:
            warn_string = "Battery is now at {} percent. Consider ending charge."
        log.warning(warn_string)

    def update_percentage(self, new_percentage):
        # If percentage and state matches that of next_warning, then warn,
        # and pop a warning from the warning generator and put it at next_warning
        # If next_warning is None, do nothing
        log.info("Battery now at {} percent".format(new_percentage))

    def update_state(self, new_state):
        # If discharge/charge changes, make a new Warning Generator to match the change
        if BATTERY_STATES[new_state] in ("Discharging", "Empty", "Pending Discharge"):
            if not self.discharging:
                self.discharging = True
                self.update_warnings()
        elif BATTERY_STATES[new_state] in ("Charging", "Fully Charged", "Pending Charge"):
            if self.discharging:
                self.discharging = False
                self.update_warnings()
        log.info("Battery is now {}".format(BATTERY_STATES[new_state]))

    def update_warnings(self):
        log.info("New warning set generated")
        self.warning_generator = self.new_warning_generator()
        self.next_warning = next(self.warning_generator, None)

    @dbus.service.method(dbus_interface=MY_IFACE)
    def Query(self):
        if self.battery is not None:
            pass

    @dbus.service.method(dbus_interface=MY_IFACE)
    def NotifyQuery(self):
        if self.battery is not None:
            pass

if __name__ == "__main__":
    from dbus.mainloop.glib import DBusGMainLoop
    from gobject import MainLoop
    DBusGMainLoop(set_as_default=True)
    BatteryMonitor(dbus.SystemBus(), dbus.SessionBus())
    MainLoop().run()

