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

NOTIFY_NAME = "org.freedesktop.Notifications"
NOTIFY_PATH = "/org/freedesktop/Notifications"
NOTIFY_IFACE = NOTIFY_NAME


class Notifier():
    class Notification():
        def __init__(self, summary, body, app_icon=None, actions=[], timeout=-1, obj=None, replaces=None):
            self._id = 0
            self._server_bus_name = None
            self.summary = summary
            self.body = body
            self.app_icon = app_icon
            # actions should be dict with { text_on_button: callback_handler }
            self.actions = actions if actions is not None else []
            self.timeout = timeout
            self.obj = obj
            self.replaces_id = replaces.id if replaces is not None else 0

    def __init__(self, session_bus, app_name, app_icon="dialog-information", default_timeout=-1):
        self._session_bus = session_bus
        self.notifications = {}

        self.app_name = app_name
        self.app_icon = app_icon
        self.default_timeout = default_timeout

        self._notifyd().connect_to_signal("NotificationClosed", self._handle_notification_closed_signal)
        self._notifyd().connect_to_signal("ActionInvoked", self._handle_action_invoked_signal)

    def _notifyd(self):
        return dbus.Interface(self._session_bus.get_object(NOTIFY_NAME, NOTIFY_PATH), NOTIFY_IFACE)

    def _handle_notification_closed_signal(self, n_id, reason):
        if n_id in self.notifications:
            del self.notifications[n_id]

    def _handle_action_invoked_signal(self, n_id, action):
        if n_id in self.notifications:
            i = None
            for i, a in enumerate(self.notifications[n_id].actions):
                if i % 2 == 0 and a == action:
                    break
            callback = self.notifications[n_id].actions[i + 1] if i is not None else None
            if callback is not None:
                callback()

    def send(self, notification):
        notifyd = self._notifyd()
        n_id = notifyd.Notify(self.app_name,
                              notification.replaces_id,
                              # Could add check here for id in self.notifications
                              notification.app_icon if notification.app_icon is not None else self.app_icon,
                              notification.summary,
                              notification.body,
                              [x for x in notification.actions[::2] for i in range(2)],
                              dict(),  # We don't add any hints
                              notification.timeout if notification.timeout != -1 else self.default_timeout)
        notification._id = n_id
        notification._server_bus_name = notifyd.bus_name
        self.notifications[n_id] = notification

    def close(self, notification):
        notifyd = self._notifyd()
        if notification._id != 0:
            if notification._server_bus_name == notifyd.bus_name:
                notifyd.CloseNotification(notification._id)
            else:
                if notification._id in self.notifications:
                    del self.notifications[notification._id]

    def close_all(self):
        for notification in self.notifications.values():
            self.close(notification)

