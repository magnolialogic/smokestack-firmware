#!/opt/smokestack-firmware/env/bin/python

"""
PID.py
https://github.com/magnolialogic/smokestack-firmware

PID controller based on proportional band in standard PID from https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
 u = Kp (e(t)+ 1/Ti INT + Td de/dt)
 PB = Proportional Band
 Ti = Goal of eliminating in Ti seconds
 Td = Predicts error value at Td in seconds
"""

import time
import SmokeLog

class PID:
	def __init__(self, PB, Ti, Td, target=0):
		self.calculate_gains(PB, Ti, Td)

		self.P = 0.0
		self.I = 0.0
		self.D = 0.0
		self.u = 0.0

		self.error = 0.0
		self.derv = 0.0
		self.inter = 0.0
		self.inter_max = abs(0.5 / self.Ki)

		self.previous_temp = target

		self.set_pid_target(self.previous_temp)

	def calculate_gains(self, PB, Ti, Td):
		self.Kp = -1 / PB
		self.Ki = self.Kp / Ti
		self.Kd = self.Kp * Td
		SmokeLog.common.debug("PB: {pb}, Ti: {ti}, Td: {td} --> Kp: {kp}, Ki: {ki}, Kd: {kd}".format(pb=PB, ti=Ti, td=Td, kp=self.Kp, ki=self.Ki, kd=self.Kd))

	def update(self, current_temp):
		#P
		error = current_temp - self.target_temp
		self.P = self.Kp * error + 0.5 #P = 1 for PB/2 under target_temp, P = 0 for PB/2 over target_temp

		#I
		time_since_last_update = time.time() - self.last_updated_time
		#if self.P > 0 and self.P < 1: #Ensure we are in the PB, otherwise do not calculate I to avoid windup
		self.inter += error * time_since_last_update
		self.inter = max(self.inter, -self.inter_max)
		self.inter = min(self.inter, self.inter_max)

		self.I = self.Ki * self.inter

		#D
		self.derv = (current_temp - self.previous_temp) / time_since_last_update
		self.D = self.Kd * self.derv

		#PID
		self.u = self.P + self.I + self.D

		#Update for next cycle
		self.error = error
		self.previous_temp = current_temp
		self.last_updated_time = time.time()

		SmokeLog.common.debug("PID: target: {target}, current: {current}, gains: ({kp}, {ki}, {kd}), errors: ({error}, {inter}, {derv}), adjustments: ({p}, {i}, {d}), pid: {u}".format(target=self.target_temp, current=current_temp, kp=self.Kp, ki=self.Ki, kd=self.Kd, error=error, inter=self.inter, derv=self.derv, p=self.P, i=self.I, d=self.D, u=self.u))

		return self.u

	def	set_pid_target(self, target_temp: float):
		self.target_temp = target_temp
		self.error = 0.0
		self.inter = 0.0
		self.derv = 0.0
		self.last_updated_time = time.time()
		SmokeLog.common.notice(target_temp)

	def set_gains(self, PB, Ti, Td):
		"""
		Unused for now, no Vapor API hooks for overriding PID gains
		"""
		self.calculate_gains(PB, Ti, Td)
		self.inter_max = abs(0.5 / self.Ki)
		SmokeLog.common.debug("new gains: ({kp}, {ki}, {kd})".format(kp=self.Kp, ki=self.Ki, kd=self.Kd))

	def get_k(self):
		return self.Kp, self.Ki, self.Kd

	def reset(self, target=0):
		self.__init__(60.0, 45.0, 180.0, target=target)

if __name__ == "__main__":
	sys.exit("I am a module, not a script.")
