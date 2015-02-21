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
from dbus.exceptions import DBusException
import sys
import logging
from gi.repository import Notify
from pybatterymonitor.pybatterymonitorconfig import VERSION, TERSE_DESCRIPTION, DEFAULT_CONFIG

log = logging.getLogger(__name__)

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
    def __init__(self, system_bus, session_bus, config_namespace):

        self.discharge_warn_values = sorted(config_namespace.discharge_warn_values, reverse=True)
        self.charge_warn_values = sorted(config_namespace.charge_warn_values, reverse=False)
        self.discharge_warn_text = config_namespace.discharge_warn_text
        self.charge_warn_text = config_namespace.charge_warn_text
        self.notification_query_summary = config_namespace.notification_query_summary
        self.notification_query_body = config_namespace.notification_query_body

        self._system_bus = system_bus
        self._session_bus = session_bus
        bus_name = dbus.service.BusName(MY_IFACE, bus=self._session_bus)
        dbus.service.Object.__init__(self, bus_name, MY_PATH)

        Notify.init("pybatterymonitor")
        self._notifications = []

        self._battery = None
        self._battery_obj = None
        self._discharging = None
        self._next_warning = None
        self._warning_generator = None

        self._init_battery()

    def _init_battery(self):
        upower = dbus.Interface(self._system_bus.get_object(UPOWER_NAME, UPOWER_PATH), UPOWER_IFACE)
        for dev_path in upower.EnumerateDevices():
            dev_obj = self._system_bus.get_object(UPOWER_NAME, dev_path)
            dev_props = dbus.Interface(dev_obj, dbus.PROPERTIES_IFACE)
            if dev_props.Get(DEV_IFACE, "Type") == DEVICE_TYPES["Battery"] and \
                           dev_props.Get(DEV_IFACE, "PowerSupply") == True:
                self._battery = dev_props
                self._battery_obj = dbus.Interface(dev_obj, "org.freedesktop.UPower.Device")
                log.info("Found battery {} {} ( {} )".format(
                    dev_props.Get(DEV_IFACE, "Vendor"),
                    dev_props.Get(DEV_IFACE, "Model"),
                    dev_path))
                self.update_state(self._battery.Get(DEV_IFACE, "State"))
                self._update_warnings()
                self.update_percentage(self._battery.Get(DEV_IFACE, "Percentage"))
                self._battery.connect_to_signal("PropertiesChanged", self._handle_battery_signal)
                break
        else:
            log.error("No Battery device found!")

    def _notification_icon(self):
        try:
            return self._battery.Get(DEV_IFACE, "IconName")
        except DBusException:
            return "dialog-information"

    def _handle_battery_signal(self, interface, data, signature):
        if "State" in data:
            self.update_state(data["State"])
        if "Percentage" in data:
            self.update_percentage(data["Percentage"])

    def _new_warning_generator(self):
        if self._discharging:
            for w in self.discharge_warn_values:
                yield w
        else:
            for w in self.charge_warn_values:
                yield w

    def _update_warnings(self):
        log.info("New warning set generated")
        for notification in self._notifications:
            notification.close()
        self._notifications.clear()
        self._warning_generator = self._new_warning_generator()
        self._next_warning = next(self._warning_generator, None)

    def _get_state(self, state_int):
        state_str = BATTERY_STATES[state_int]
        if state_str in ("Discharging", "Empty", "Pending Discharge"):
            discharging = True
        elif state_str in ("Charging", "Fully Charged", "Pending Charge"):
            discharging = False
        return discharging, state_str

    def update_state(self, new_state):
        # If discharge/charge changes, make a new Warning Generator to match the change
        discharging_new, state_str = self._get_state(new_state)
        if self._discharging != discharging_new:
            self._discharging = discharging_new
            self._update_warnings()
        log.info("- new state: {}".format(state_str))

    def update_percentage(self, new_percentage):
        # If percentage and state matches that of next_warning, then warn,
        # and pop a warning from the warning generator and put it at next_warning
        # If next_warning is None, do nothing
        log.info("- new percentage: {}".format(new_percentage))
        if self._next_warning is not None:
            if self._discharging:
                if new_percentage <= self._next_warning:
                    self.warn(new_percentage)
                    w = None
                    for w in self._warning_generator:
                        if w < new_percentage:
                            break
                        log.info("   - catching up, discarding {}".format(w))
                    self._next_warning = w
            else:
                if new_percentage >= self._next_warning:
                    self.warn(new_percentage)
                    w = None
                    for w in self._warning_generator:
                        if w > new_percentage:
                            break
                        log.info("   - catching up, discarding {}".format(w))
                    self._next_warning = w
        log.info("- next warning: {}".format(self._next_warning))

    def warn(self, percentage):
        if self._discharging:
            text = self.discharge_warn_text
        else:
            text = self.charge_warn_text
        notification = Notify.Notification.new("{}%".format(percentage), text, self._notification_icon())
        notification.add_action("suppress_future", "Suppress Future", self.suppress_future)
        notification.add_action("dismiss", "Dismiss", lambda n, a: n.close())
        self._notifications.append(notification)
        notification.show()
        log.info("Battery is now at {} percent. {}".format(percentage, text))

    def suppress_future(self, notification, action_name):
        log.info("Suppressing future warnings for this state change")
        self._next_warning = None
        log.info("- next warning: {}".format(self._next_warning))

    @dbus.service.method(dbus_interface=MY_IFACE)
    def Query(self):
        log.info("Recieved method call Query")
        # Refreshing device data requires org.freedesktop.upower.refresh-power-source authorization (via polkit)
        log.debug("Refreshing UPower device data...")
        self._battery_obj.Refresh()
        state_int = self._battery.Get(DEV_IFACE, "State")
        discharging, state_str = self._get_state(state_int)
        sign = '-' if discharging else "+"
        return {"vendor": self._battery.Get(DEV_IFACE, "Vendor"),
                "model": self._battery.Get(DEV_IFACE, "Model"),
                "percentage": self._battery.Get(DEV_IFACE, "Percentage"),
                "power": self._battery.Get(DEV_IFACE, "EnergyRate"),
                "energy": self._battery.Get(DEV_IFACE, "Energy"),
                "voltage": self._battery.Get(DEV_IFACE, "Voltage"),
                "state": state_str,
                "sign": sign}

    @dbus.service.method(dbus_interface=MY_IFACE)
    def NotifyQuery(self, notification=Notify.Notification.new("", "", "")):
        query_results = self.Query()
        notification.update(self.notification_query_summary.format(**query_results),
                            self.notification_query_body.format(**query_results),
                            self._notification_icon())
        notification.show()


def _parse_args(options=None):
    # Command-line arguments
    import argparse
    a_parser = argparse.ArgumentParser(prog="pybatterymonitor",
                                       description=TERSE_DESCRIPTION)
    a_parser.add_argument("-dvals", "--discharge-warn-values", metavar='VALUES', type=int, nargs='+',
                          help="battery percentages at which to trigger notifications when discharging")
    a_parser.add_argument("-cvals", "--charge-warn-values", metavar='VALUES', type=int, nargs='+',
                          help="battery percentages at which to trigger notifications when charging")
    a_parser.add_argument("-dwarn", "--discharge-warn-text", metavar='TEXT', type=str,
                          help="the text in notifications triggered while discharging")
    a_parser.add_argument("-cwarn", "--charge-warn-text", metavar='TEXT', type=str,
                          help="the text in notifications triggered while charging")
    a_parser.add_argument("-qsummary", "--notification-query-summary", metavar='SUMMARY', type=str,
                          help="format string of the summary/title of the notification shown upon query")
    a_parser.add_argument("-qbody", "--notification-query-body", metavar='BODY', type=str,
                          help="format string of the body of the notification shown upon query")
    a_parser.add_argument("--config-file", metavar="CONFIG_FILE", type=str,
                          help="configuration file to use")
    a_parser.add_argument("--version", action='version', version="%(prog)s v{}".format(VERSION))
    a_parser.add_argument("--verbose", action='store_true')
    a_parser.add_argument("--debug", action='store_true')

    # Parse the arguments
    log.debug("Parsing command-line arguments...")
    if options is None:
        args = a_parser.parse_args()
    else:
        args = a_parser.parse_args(options)

    # Adjust log to match verbosity level given and attach an appropriate handler
    if args.debug or args.verbose:
        log.setLevel(logging.DEBUG if args.debug else logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        log.addHandler(handler)
    else:
        log.setLevel(logging.WARNING)
        error_handler = logging.StreamHandler(sys.stderr)
        log.addHandler(error_handler)

    log.debug("Recieved command-line arguments: {}".format(vars(args)))

    # Config file
    import os.path
    if args.config_file is None:
        args.config_file = os.path.expanduser("~") + "/.config/pybatterymonitor.conf"
    if os.path.isfile(args.config_file):
        log.info("Config file found at " + args.config_file)
        import configparser
        c_parser = configparser.ConfigParser()
        log.debug("Reading config file...")
        c_parser.read(args.config_file)
        if "pybatterymonitor" in c_parser.sections():
            sections = c_parser["pybatterymonitor"]
            for c in sections:
                log.debug("Processing config file option '{}'".format(c))
                if c not in args or getattr(args, c) is None:
                    if "warn_values" in c:  # if this config is a list (must parse manually)
                        target = [int(i) for i in sections[c].strip().split(" ")]
                    else:
                        target = sections[c]
                    setattr(args, c, target)

    # Defaults
    for c in DEFAULT_CONFIG:
        if c not in args or getattr(args, c) is None:
            log.debug("Using defualt config for '{}'".format(c))
            setattr(args, c, DEFAULT_CONFIG[c])

    return args


def entry_point(options=None):
    args = _parse_args(options)
    BatteryMonitor(dbus.SystemBus(), dbus.SessionBus(), args)


def main(options=None):
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository.GObject import MainLoop

    DBusGMainLoop(set_as_default=True)
    entry_point(options)
    MainLoop().run()


if __name__ == "__main__":
    main()
