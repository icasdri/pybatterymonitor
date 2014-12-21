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

VERSION = 0.2
DEFAULT_CONFIG = {"discharge_warn_values": [i for i in range(0, 41, 5)],
                  "charge_warn_values": [i for i in range(80, 101, 5)],
                  "discharge_warn_text": "Consider ending discharge.",
                  "charge_warn_text": "Consider ending charge."}
TERSE_DESCRIPTION = "Daemon for monitoring and notifying about battery levels."
DESCRIPTION = "A small user daemon for GNU/Linux that monitors battery levels and notifies users"