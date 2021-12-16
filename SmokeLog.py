#!/opt/smokestack-firmware/env/bin/python

"""
SmokeLog.py
https://github.com/magnolialogic/smokestack-firmware
"""

import syslog
import sys

class SmokeLog:
	"""
	Syslog logger for Smokestack firmware
	"""

	def __init__(self):
		syslog.openlog(ident="smokestack", logoption=syslog.LOG_PID, facility=syslog.LOG_DAEMON)

	def syslog_formatted(sender, message):
		"""
		Prints message to STDOUT and then condenses whitespace + removes newlines to clean up syslog output
		"""
		unformatted_string = f"{sender}: {message}"
		print(unformatted_string.rstrip())
		formatted_message = unformatted_string.replace("\n", "")
		return " ".join(formatted_message.split())

	@staticmethod
	def debug(message):
		"""
		Send message to syslog with Debug priority
		"""
		sender = sys._getframe(1).f_code.co_name
		syslog.syslog(syslog.LOG_DEBUG, SmokeLog.syslog_formatted(sender, message))

	@staticmethod
	def info(message):
		"""
		Send message to syslog with Info priority
		"""
		sender = sys._getframe(1).f_code.co_name
		syslog.syslog(syslog.LOG_INFO, SmokeLog.syslog_formatted(sender, message))

	@staticmethod
	def notice(message):
		"""
		Send message to syslog with Notice priority
		"""
		sender = sys._getframe(1).f_code.co_name
		syslog.syslog(syslog.LOG_NOTICE, SmokeLog.syslog_formatted(sender, message))

	@staticmethod
	def error(message):
		"""
		Send message to syslog with Error priority
		"""
		sender = sys._getframe(1).f_code.co_name
		syslog.syslog(syslog.LOG_ERR, SmokeLog.syslog_formatted(sender, message))

	@staticmethod
	def pretty_request(status_code, message):
		"""
		Convenience method consistently formats HTTP response status code and response message
		"""
		request_summary = f"Status {status_code}: {message}"
		return request_summary

common = SmokeLog() # Create shared / singleton logger

if __name__ == "__main__":
	sys.exit("I am a module, not a script.")