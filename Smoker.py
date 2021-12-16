#!/opt/smokestack-firmware/env/bin/python

"""
Smoker.py
https://github.com/magnolialogic/smokestack-firmware
"""

import sys
import time
import RPi.GPIO as GPIO
from PID import PID
import SmokeLog
import TempSensor

class Smoker:
	"""
	Smoker state machine for Smokestack firmware
	"""
	def __init__(self):
		SmokeLog.common.info("FIRE IT UP")
		self.relays = {
			"auger": 16,
			"fan": 13,
			"igniter": 18
		}
		self.sensors = {
			"probe": TempSensor.MAX31855(chip_select=1),
			"grill": TempSensor.MAX31865(chip_select=0)
		}
		self.connected = False
		self.program_id = None
		self.program_index = None
		self.program_steps = []
		self.p_setting = 2
		self.timers = {}
		self.timers["last_pid_update"] = None
		self.timers["last_heartbeat"] = None
		self.timers["last_toggled"] = {}
		self.grill_history = []
		self.average_for_pid = None
		self.initialize()

	def initialize(self):
		"""
		Reset Smoker state during startup or shutdown
		"""
		time_startup = time.time()
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		self.thermocouple_connected = self.sensors["probe"].connected
		self.timers["boot"] = time_startup
		self.timers["last_program_started"] = time_startup
		self.state = {
			"mode": "Idle",
			"online": self.connected,
			"power": False,
			"temps": {
				"grillCurrent": self.sensors["grill"].read(),
				"grillTarget": None,
				"probeCurrent": None,
				"probeTarget": None
				},
			"probeConnected": self.thermocouple_connected
		}
		self.pid_values = { #60, 45, 180 holds +- 5F
			"PB": 60.0,
			"Td": 45.0,
			"Ti": 180.0,
			"u": 0.15,
			"cycle_timer": 20
		}
		self.pid = PID(self.pid_values["PB"], self.pid_values["Ti"], self.pid_values["Td"])
		for key in self.relays:
			GPIO.setup(self.relays[key], GPIO.OUT)
			self.set_relay(key, False)
		SmokeLog.common.notice("done")

	def get_state(self, relay):
		"""
		Returns Boolean for GPIO state
		"""
		state = GPIO.input(self.relays[relay])
		if state == 0:
			return False
		return True

	def set_relay(self, relay, target_state):
		"""
		Set GPIO to target_state
		"""
		if not self.get_state(relay) == target_state:
			SmokeLog.common.debug("{relay} {current_state} -> {target_state}".format(relay=relay, current_state=self.get_state(relay), target_state=target_state))
			self.timers["last_toggled"][relay] = time.time()
			GPIO.output(self.relays[relay], target_state)

	def timer_expired(self, timer, timeout):
		"""
		Returns Boolean indicating whether given timeout has fired for given timer
		"""
		if self.timers[timer] is None or time.time() - self.timers[timer] > timeout:
			return True
		else:
			return False

	def set_pause_cycle(self, pSetting=2):
		"""
		Set pause time for auger in Smoke mode
		http://tipsforbbq.com/Definition/Traeger-P-Setting
		"""
		auger_on = 15
		auger_off = 45 + pSetting * 10
		self.pid_values["cycle_timer"] = auger_on + auger_off
		self.pid_values["u"] = auger_on / (auger_on + auger_off)

	def read_temps(self):
		"""
		Read and log current temperatures
		"""
		grill_current = self.sensors["grill"].read()
		self.state["temps"]["grillCurrent"] = grill_current
		self.grill_history.append(grill_current)
		self.grill_history = self.grill_history[-6:]
		self.average_for_pid = sum(self.grill_history) / len(self.grill_history)
		self.state["temps"]["probeCurrent"] = self.sensors["probe"].read()

if __name__ == "__main__":
	sys.exit("I am a module, not a script.")