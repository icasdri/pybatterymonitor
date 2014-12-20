# Copyright 2014 icasdri
#
# This file is part of pybatterymonitor.
#
# pybatterymonitor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pybatterymonitor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pybatterymonitor.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'icasdri'

import dbus
import dbus.service
import sys
import logging
from pybatterymonitor.notifier import Notifier

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

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
    def __init__(self, system_bus, session_bus,
                 discharge_warn_values, charge_warn_values,
                 discharge_warn_text, charge_warn_text):

        self.discharge_warn_values = sorted(discharge_warn_values, reverse=True)
        self.charge_warn_values = sorted(charge_warn_values, reverse=False)

        self.discharge_warn_text = discharge_warn_text
        self.charge_warn_text = charge_warn_text

        self.system_bus = system_bus
        self.session_bus = session_bus
        bus_name = dbus.service.BusName(MY_IFACE, bus=self.session_bus)
        dbus.service.Object.__init__(self, bus_name, MY_PATH)

        self.notifier = Notifier(self.session_bus, "pybatterymonitor")

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
                log.info("Found battery {} {}".format(
                    dev_props.Get(DEV_IFACE, "Vendor"),
                    dev_props.Get(DEV_IFACE, "Model")))
                self.update_state(self.battery.Get(DEV_IFACE, "State"))
                self.update_warnings()
                self.update_percentage(self.battery.Get(DEV_IFACE, "Percentage"))
                self.battery.connect_to_signal("PropertiesChanged", self.handle_battery_signal)
                break
        else:
            log.error("No Battery device found!")

    def handle_battery_signal(self, interface, data, signature):
        if "State" in data:
            self.update_state(data["State"])
        if "Percentage" in data:
            self.update_percentage(data["Percentage"])

    def new_warning_generator(self):
        if self.discharging:
            for w in self.discharge_warn_values:
                yield w
        else:
            for w in self.charge_warn_values:
                yield w

    def warn(self, percentage):
        if self.discharging:
            text = "Consider ending discharge."
        else:
            text = "Consider ending charge."
        self.notifier.send(Notifier.Notification("{}%".format(percentage),
                                                 text,
                                                 app_icon=None,
                                                 actions=["Suppress Future", self.suppress_future,
                                                          "Dismiss", None]))
        log.warning("WARNING: Battery is now at {} percent. {}".format(percentage, text))

    def suppress_future(self):
        log.info("Suppressing future warnings for this state change")
        self.next_warning = None
        log.info("- next warning: {}".format(self.next_warning))

    def update_percentage(self, new_percentage):
        # If percentage and state matches that of next_warning, then warn,
        # and pop a warning from the warning generator and put it at next_warning
        # If next_warning is None, do nothing
        log.info("- new percentage: {}".format(new_percentage))
        if self.next_warning is not None:
            if self.discharging:
                if new_percentage <= self.next_warning:
                    self.warn(new_percentage)
                    w = None
                    for w in self.warning_generator:
                        if w < new_percentage:
                            break
                        log.info("   - catching up, discarding {}".format(w))
                    self.next_warning = w
            else:
                if new_percentage >= self.next_warning:
                    self.warn(new_percentage)
                    w = None
                    for w in self.warning_generator:
                        if w > new_percentage:
                            break
                        log.info("   - catching up, discarding {}".format(w))
                    self.next_warning = w
        log.info("- next warning: {}".format(self.next_warning))

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
        log.info("- new state: {}".format(BATTERY_STATES[new_state]))

    def update_warnings(self):
        log.info("New warning set generated")
        self.notifier.close_all()
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

def parse_and_get_args():
    # Command-line arguments
    import argparse
    a_parser = argparse.ArgumentParser(prog="pybatterymonitor",
                                     description="Daemon for monitoring and notifying about battery levels.")
    a_parser.add_argument("-dvals", "--discharge-warn-values", metavar='VALUES', type=int, nargs='+',
                        help="battery percentages at which to trigger notifications when discharging")
    a_parser.add_argument("-cvals", "--charge-warn-values", metavar='VALUES', type=int, nargs='+',
                        help="battery percentages at which to trigger notifications when charging")
    a_parser.add_argument("-dwarn", "--discharge-warn-text", metavar='TEXT', type=str,
                        help="the text in notifications triggered while discharging")
    a_parser.add_argument("-cwarn", "--charge-warn-text", metavar='TEXT', type=str,
                        help="the text in notifications triggered while charging")
    a_parser.add_argument("--config-file", metavar="CONFIG_FILE", type=str,
                        help="configuration file to use")
    a_parser.add_argument("--version", action='version', version="%(prog)s v0.2")
    a_parser.add_argument("--verbose", action='store_true')
    args = a_parser.parse_args()

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(logging.DEBUG if args.verbose else logging.WARNING)
    log.addHandler(_handler)

    # Config file
    import os.path
    if args.config_file is None:
        args.config_file = os.path.expanduser("~") + "/.config/pybatterymonitor.conf"
    if os.path.isfile(args.config_file):
        log.info("Config file found at " + args.config_file)
        import configparser
        c_parser = configparser.ConfigParser()
        c_parser.read(args.config_file)
        if "pybatterymonitor" in c_parser.sections():
            sections = c_parser["pybatterymonitor"]
            for c in sections:
                log.debug("Processing config \"" + c + "\"")
                if c not in args or getattr(args, c) is None:
                    setattr(args, c, DEFAULT_CONFIG[c])

    # Defaults
    for c in DEFAULT_CONFIG:
        if c not in args or getattr(args, c) is None:
            setattr(args, c, DEFAULT_CONFIG[c])

    return args

DEFAULT_CONFIG = {"discharge_warn_values": [i for i in range(0, 41, 5)],
                  "charge_warn_values": [i for i in range(80, 101, 5)],
                  "discharge_warn_text": "Consider ending discharge.",
                  "charge_warn_text": "Consider ending charge."}

def main():
    args = parse_and_get_args()

    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository.GObject import MainLoop

    DBusGMainLoop(set_as_default=True)
    print(args.charge_warn_text)
    BatteryMonitor(dbus.SystemBus(), dbus.SessionBus(),
                   args.discharge_warn_values, args.charge_warn_values,
                   args.discharge_warn_text, args.charge_warn_text)
    MainLoop().run()


if __name__ == "__main__":
    main()
