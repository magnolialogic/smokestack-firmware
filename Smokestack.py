#!/opt/smokestack-firmware/env/bin/python

"""
Smokestack.py
https://github.com/magnolialogic/smokestack-firmware
"""

import copy
import json
import os
import requests
import SmokeLog
import Smoker
import sys
import time
import traceback
import yaml

# MARK: CONSTANTS

SMOKESTACK_USERNAME = "firmware"
SMOKESTACK_FIRMWARE_PATH = os.path.dirname(os.path.realpath(__file__)) #whereami
SMOKESTACK_FIRMWARE_VERSION = "2.0.0a (2021.12.15)"
FREQUENCY_POST_BOOT = 10		# Period (s) between calls to /smoker/boot during startup
FREQUENCY_LOG_TEMPS = 10		# Period (s) between temperature measurements
FREQUENCY_UPDATE_PID = 20		# Period (s) between control loop updates during Hold mode
FREQUENCY_IDLE_TIMER = 0.25		# Period (s) between main runloop cycles
TEMPERATURE_IGNITER = 100		# Upper limit (°F) of grill temperatures that trigger the igniter
TEMPERATURE_START = 140			# Temp limit (°F) to indicate we've finished Start mode and it's OK to transition into Hold
TIMEOUT_IGNITER = 15 * 60		# Maximum time (s) igniter should be on
TIMEOUT_SHUTDOWN = 10 * 60		# Time (s) to run fan after shutdown
U_MIN = 0.15 					# Maintenance levels
U_MAX = 1.0

# MARK: NETWORKING METHODS

def post_boot():
	"""
	POST /smoker/boot

	Called on boot, posts firmware version ("Firmware-Version" header) and initial state (body)
	"""
	route = SMOKESTACK_API_ROOT + "/smoker/boot"
	try:
		smoker.state["online"] = True
		boot_json = copy.deepcopy(smoker.state)
		boot_json["temps"] = {k: v for k, v in boot_json["temps"].items() if v is not None}
		SmokeLog.common.info(boot_json)
		response = requests.post(route, headers={"Firmware-Version": SMOKESTACK_FIRMWARE_VERSION}, json=boot_json, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("{code}: request failed to initialize state! {error}".format(code=response.status_code, error=response.text)))
	else:
		if response.ok:
			SmokeLog.common.info("ok")
			smoker.connected = True
		else:
			SmokeLog.common.error("{code} vapor offline".format(code=response.status_code))
			smoker.connected = False

def post_heartbeat():
	"""
	POST /smoker/heartbeat

	Posts latest grill temp and (optionally) probe temp
	Vapor optionally returns state or program based on pending interrupt
	"""
	route = SMOKESTACK_API_ROOT + "/smoker/heartbeat"
	if smoker.timer_expired("last_heartbeat", FREQUENCY_LOG_TEMPS):
		heartbeat_json = copy.deepcopy(smoker.state)
		heartbeat_json["temps"] = {k: v for k, v in smoker.state["temps"].items() if v is not None}
		smoker.timers["last_heartbeat"] = time.time()
		SmokeLog.common.info(heartbeat_json)
		try:
			response = requests.post(route, headers={"Firmware-Version": SMOKESTACK_FIRMWARE_VERSION}, json=heartbeat_json, auth=requests.auth.HTTPBasicAuth("firmware", SMOKESTACK_PASSWORD))
		except Exception:
			smoker.connected = False
			SmokeLog.common.error("request caught exception!")
		else:
			if response.ok:
				smoker.connected = True
				SmokeLog.common.info("ok")
				if response.json()["program"] != None:
					handle_program_update(response.json()["program"])
				if response.json()["state"] != None:
					handle_state_update(response.json()["state"])
			else:
				SmokeLog.common.error("vapor error: {error}".format(error=response.status_code))

def put_state():
	"""
	Push current state to remote DB (complete replacement)
	"""
	route = SMOKESTACK_API_ROOT + "/state"
	try:
		response = requests.put(route, json=smoker.state, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("failed to push updated state! {error}".format(error=traceback.format_exc())))
	else:
		smoker.timers["last_state_push"] = time.time()
		if response.ok:
			SmokeLog.common.info("ok {response}".format(response=smoker.state))
		else:
			SmokeLog.common.error("vapor error: {error}".format(error=response.status_code))

def patch_state(patch_data):
	"""
	Patch specific state keys in remote DB
	"""
	route = SMOKESTACK_API_ROOT + "/state"
	try:
		response = requests.patch(route, json=patch_data, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("failed to patch state! {error}".format(error=traceback.format_exc())))
	else:
		if response.ok:
			SmokeLog.common.info("ok {response}".format(response=patch_data))
		else:
			SmokeLog.common.error("status {code}: failed to patch state! {error}".format(code=response.status_code, error=response.text.translate(str.maketrans("", "", "\"'"))))

def check_for_program_id():
	"""
	Check whether program exists in remote DB
	"""
	route = SMOKESTACK_API_ROOT + "/program"
	try:
		response = requests.get(route, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("failed to get program! {error}".format(error=traceback.format_exc())))
	else:
		if response.ok:
			SmokeLog.common.notice("found {id}".format(id=response.text))
			get_steps_for_id(response.text)
		else:
			SmokeLog.common.info(response.status_code)

def get_steps_for_id(id):
	"""
	Get program data from remote DB
	"""
	route = SMOKESTACK_API_ROOT + "/program/" + id
	try:
		response = requests.get(route, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("failed to get program! {error}".format(error=traceback.format_exc())))
	else:
		if response.ok:
			smoker.program_id = id
			smoker.program_index = 0
			smoker.program_steps = response.json()
			SmokeLog.common.info("found {steps}".format(steps=smoker.program_steps))
		else:
			SmokeLog.common.error("status {code}: no program found".format(code=response.status_code))

def delete_program():
	"""
	Clear all programs in remote DB
	"""
	route = SMOKESTACK_API_ROOT + "/smoker/program"
	try:
		response = requests.delete(route, auth=requests.auth.HTTPBasicAuth(SMOKESTACK_USERNAME, SMOKESTACK_PASSWORD))
	except Exception:
		sys.exit(SmokeLog.common.error("failed to delete program! {error}".format(error=traceback.format_exc())))
	else:
		if response.ok:
			smoker.timers["last_program_push"] = time.time()
			SmokeLog.common.info("ok")
		else:
			SmokeLog.common.error("status {code}: failed to delete program! {error}".format(code=response.status_code, error=response.text.translate(str.maketrans("", "", "\"'"))))

# MARK: HEARTBEAT HANDLERS

def handle_program_update(new_program):
	"""
	Handle newly received program
	"""
	if new_program["id"] != smoker.program_id:
		SmokeLog.common.notice(new_program)
		smoker.program_id = new_program["id"]
		smoker.program_index = 0
		smoker.program_steps = new_program["steps"]
		skip_start_mode = smoker.state["power"] and smoker.state["mode"] in ["Smoke", "Hold"]
		if skip_start_mode and new_program_data[0]["mode"] == "Start":
			SmokeLog.common.info("skipping Start program since smoker has alredy warmed up")
			smoker.program_index = 1
		if smoker.state["power"]:
			set_program()
	else:
		SmokeLog.common.info("new program matches existing program, ignoring")

def handle_state_update(new_state):
	"""
	Evaluate new state from remote DB and update smoker state if necessary
	"""
	def state_changed(key, old_value, new_value):
		SmokeLog.common.info("{key} {old_value} -> {new_value}".format(key=key, old_value=old_value, new_value=new_value))

	SmokeLog.common.notice(new_state)
	if new_state["mode"] != smoker.state["mode"]:
		state_changed("mode", smoker.state["mode"], new_state["mode"])
		smoker.state["mode"] = new_state["mode"]
		smoker.state["temps"]["grillTarget"] = new_state["temps"]["grillTarget"] # TODO: fix this! what if a temp is None??
		set_mode(new_state["mode"])
	if new_state["temps"]["grillTarget"] != smoker.state["temps"]["grillTarget"]:
		if new_state["temps"]["grillTarget"] is None and new_state["mode"] not in ["Idle", "Off", "Shutdown"]:
			SmokeLog.common.error("Invalid grillTarget (None) for mode {new_mode}".format(new_mode=new_state["mode"]))
		if new_state["temps"]["grillTarget"] is None and new_state["mode"] in ["Start", "Hold", "Smoke"]:
			state_changed("grillTarget", smoker.state["temps"]["grillTarget"], new_state["temps"]["grillTarget"])
			smoker.state["temps"]["grillTarget"] = new_state["temps"]["grillTarget"]
			smoker.pid.set_pid_target(float(new_state["grillTarget"]))
	if new_state["temps"]["probeTarget"] != smoker.state["temps"]["probeTarget"]:
		state_changed("probeTarget", smoker.state["temps"]["probeTarget"], new_state["temps"]["probeTarget"])
		for key, value in new_state["temps"].items():
			smoker.state["temps"][key] = value
	if new_state["power"] != smoker.state["power"]:
		state_changed("power", smoker.state["power"], new_state["power"])
		if new_state["power"] and len(smoker.program_steps) == 0:
			SmokeLog.common.notice("no program exists, rejecting program control! 1 -> 0")
			smoker.state["power"] = False
			patch_state({"power": False})
		elif not new_state["power"] and new_state["mode"] == "Off":
			sys.exit(SmokeLog.common.notice("program stopped and mode == Off, shutting down smoker."))
		elif not new_state["power"] and len(smoker.program_steps) > 0:
			SmokeLog.common.notice("suspending program control")
			smoker.state["power"] = False
			smoker.timers["last_program_started"] = time.time()
		elif len(smoker.program_steps) > 0:
			smoker.state["power"] = new_state["power"]
			set_program()

# MARK: STATE MANAGEMENT

def read_temps():
	"""
	Read temperature sensors and record measurements if necessary
	"""
	if smoker.state["temps"]["grillCurrent"] is None or smoker.timer_expired("last_heartbeat", FREQUENCY_LOG_TEMPS):
		smoker.read_temps()

def manage_igniter():
	"""
	Check whether igniter has been on for too long or needs to be enabled/disabled due to crossing TEMPERATURE_IGNITER threshold
	"""
	if smoker.get_state("igniter") and time.time() - smoker.timers["last_toggled"]["igniter"] > TIMEOUT_IGNITER:
		SmokeLog.common.error("disabling igniter due to timeout!")
		smoker.set_relay("igniter", False)
		set_mode("Shutdown")
		smoker.timers["last_program_started"] = time.time()
	elif not smoker.get_state("igniter") and smoker.state["temps"]["grillCurrent"] < TEMPERATURE_IGNITER:
		SmokeLog.common.notice("enabling igniter due to low temp: {temp} < {limit}".format(temp=smoker.state["temps"]["grillCurrent"], limit=TEMPERATURE_IGNITER))
		smoker.set_relay("igniter", True)
	elif smoker.get_state("igniter") and smoker.state["temps"]["grillCurrent"] > TEMPERATURE_IGNITER:
		SmokeLog.common.notice("disabling igniter due to high temp: {temp} > {limit}".format(temp=smoker.state["temps"]["grillCurrent"], limit=TEMPERATURE_IGNITER))
		smoker.set_relay("igniter", False)

def manage_auger():
	"""
	Check whether auger needs to be started or stopped based on PID duty cycle
	"""
	if smoker.get_state("auger") and time.time() - smoker.timers["last_toggled"]["auger"] > smoker.pid_values["cycle_timer"] * smoker.pid_values["u"] and smoker.pid_values["u"] < 1.0: # Auger currently on AND TimeSinceToggle > auger On Time AND maintenance not continuous
		smoker.set_relay("auger", False)
	elif not smoker.get_state("auger") and time.time() - smoker.timers["last_toggled"]["auger"] > smoker.pid_values["cycle_timer"] * (1 - smoker.pid_values["u"]): # Auger currently off AND TimeSinceToggle > auger Off Time
		smoker.set_relay("auger", True)

def set_mode(new_mode): # pylint: disable=R0915
	"""
	Update smoker state to match new_mode, and post update to Vapor
	"""
	SmokeLog.common.notice(new_mode)
	smoker.state["mode"] = new_mode
	if new_mode == "Off":
		patch_state({"mode": "Off", "temps": {"grillTarget": None, "probeTarget": None}})
		sys.exit(SmokeLog.common.notice("restarting smoker..."))
	elif new_mode == "Shutdown":
		smoker.state["power"] = False
		smoker.timers["last_program_started"] = time.time()
		smoker.set_relay("fan", True)
		smoker.set_relay("auger", False)
		smoker.set_relay("igniter", False)
		smoker.state["power"] = False
		smoker.program_steps = []
		smoker.state["temps"]["grillTarget"] = None
		delete_program()
	elif new_mode == "Start":
		smoker.state["power"] = True
		smoker.set_relay("fan", True)
		smoker.set_relay("auger", True)
		smoker.set_relay("igniter", True)
		smoker.pid_values["cycle_timer"] = 15 + 45
		smoker.pid_values["u"] = 15.0 / (15.0 + 45.0) #P0
		smoker.pid.reset(target=smoker.state["temps"]["grillTarget"])
	elif new_mode == "Smoke":
		SmokeLog.common.debug("using p-setting {p_setting}".format(p_setting=smoker.p_setting))
		smoker.set_relay("fan", True)
		smoker.set_relay("auger", True)
		manage_igniter()
		smoker.set_pause_cycle(smoker.p_setting)
	elif new_mode == "Hold":
		smoker.set_relay("fan", True)
		smoker.set_relay("auger", True)
		manage_igniter()
		smoker.pid_values["cycle_timer"] = FREQUENCY_UPDATE_PID
		smoker.pid_values["u"] = U_MIN

	put_state()

def run_mode():
	"""
	Main loop actions for each mode
	"""
	if smoker.state["mode"] in ["Start", "Smoke", "Hold", "Keep Warm"]:
		manage_igniter()
		manage_auger()
	if smoker.state["mode"] in ["Hold", "Keep Warm"]:
		update_pid()

def update_pid():
	"""
	Handle newly received 60s average grill temperature, and update PID we're in Hold mode
	"""
	if smoker.state["mode"] == "Hold" and smoker.timer_expired("last_pid_update", FREQUENCY_UPDATE_PID):
		smoker.pid_values["u"] = smoker.pid.update(smoker.average_for_pid)	# Update u based on provided average of temps from last 60s
		smoker.pid_values["u"] = max(smoker.pid_values["u"], U_MIN)			# Ensure updated u >= U_MIN
		smoker.pid_values["u"] = min(smoker.pid_values["u"], U_MAX)			# Ensure updated u <= U_MAX
		SmokeLog.common.debug("updated u: {u}".format(u=smoker.pid_values["u"]))
		smoker.timers["last_pid_update"] = time.time()

def monitor_limits():
	"""
	Check whether program limit has been reached
	"""

	if smoker.state["power"] and len(smoker.program_steps) >= smoker.program_index+1:
		finished = False
		if smoker.program_steps[smoker.program_index]["trigger"] == "Time":
			if time.time() - smoker.timers["last_program_started"] > smoker.program_steps[smoker.program_index]["limit"]:
				finished = True
				SmokeLog.common.notice("timer expired")
		elif smoker.program_steps[smoker.program_index]["trigger"] == "Temp" and smoker.state["temps"]["probeCurrent"] is not None:
			if smoker.state["temps"]["probeCurrent"] > smoker.program_steps[smoker.program_index]["limit"]:
				finished = True
				SmokeLog.common.notice("probe reached requested temperature")
		if finished:
			next_program()

	if smoker.state["mode"] == "Shutdown" and smoker.timer_expired("last_program_started", TIMEOUT_SHUTDOWN):
		SmokeLog.common.notice("shutdown timer expired, setting mode to Off")
		set_mode("Off")

def set_program():
	"""
	Apply settings from current program
	"""
	if smoker.state["power"] and len(smoker.program_steps) > 0 and smoker.program_index != None:
		SmokeLog.common.notice(smoker.program_steps[smoker.program_index])
		smoker.state["temps"]["grillTarget"] = smoker.program_steps[smoker.program_index]["targetGrill"]
		if smoker.program_steps[smoker.program_index]["trigger"] == "Temp":
			if not smoker.state["probeConnected"]:
				SmokeLog.common.notice("no probe connected, rejecting program with temp limit")
				smoker.state["power"] = False
				patch_state({"power": False})
			smoker.state["temps"]["probeTarget"] = smoker.program_steps[smoker.program_index]["limit"]
		else:
			smoker.state["temps"]["probeTarget"] = None
		smoker.pid.set_pid_target(smoker.state["temps"]["grillTarget"])
		set_mode(smoker.program_steps[smoker.program_index]["mode"])
	else:
		if len(smoker.program_steps) > 0 and not smoker.state["power"]:
			SmokeLog.common.notice("program mode disabled! clearing remaining programs")
			smoker.program_steps = []
		elif len(smoker.program_steps) == 0 and smoker.state["power"]:
			SmokeLog.common.notice("no program found! Disabling program control")
			smoker.state["power"] = False
			set_mode("Hold")
		elif smoke.program_index == None:
			SmokeLog.common.error("failed to apply program, program_index is missing. disabling program control and clearing program.")
			smoker.state["power"] = False
			smoker.program_steps = []
			set_mode("Hold")
		smoker.state["temps"]["probeTarget"] = None
		if smoker.state["mode"] in ["Idle", "Start", "Hold", "Smoke"]:
			set_mode("Shutdown")

	smoker.timers["last_program_started"] = time.time()

def next_program():
	"""
	End current program and advance to next, if one exists
	"""
	if len(smoker.program_steps) > smoker.program_index+1: # There is at least one more program available
		SmokeLog.common.notice("running next program")
		smoker.program_index += 1
		set_program()
	elif len(smoker.program_steps) == smoker.program_index+1:
		SmokeLog.common.notice("finished last step in program, shutting down")
		set_mode("Shutdown")
	else:
		sys.exit(SmokeLog.common.error("invalid program index, exiting"))


# MARK: MAIN

if __name__ == "__main__":
	"""
	Configure Smoker and establish connection to Vapor
	"""
	with open(os.path.join(SMOKESTACK_FIRMWARE_PATH, "config.yaml")) as config_file:
		try:
			config = yaml.safe_load(config_file)
		except yaml.YAMLError:
			sys.exit(yaml.YAMLError)
		else:
			SMOKESTACK_API_ROOT = config["api-url"].rstrip() + "/api"
			SMOKESTACK_PASSWORD = config["api-key"].rstrip()

	smoker = Smoker.Smoker()

	while not smoker.connected:
		post_boot()
		if not smoker.connected: time.sleep(FREQUENCY_POST_BOOT)

	check_for_program_id()

	while True:
		read_temps()
		monitor_limits()
		post_heartbeat()
		run_mode()
		time.sleep(FREQUENCY_IDLE_TIMER)