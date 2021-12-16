#!/opt/smokestack-firmware/env/bin/python

"""
TempSensor.py
https://github.com/magnolialogic/smokestack-firmware
Adapted from MIT-Licenses work at https://github.com/adafruit
"""

import time
import math
import sys
import spidev
import SmokeLog

class MAX31855:
	"""
	MAX31855 thermocouple driver
	"""
	def __init__(self, chip_select):
		"""
		Initialize MAX31855 device with hardware SPI on specified chip-select pin
		"""
		self.connected = False
		self.chip_select = chip_select
		self.linear = True
		self.spi = spidev.SpiDev()
		self.spi.open(0, chip_select)
		self.spi.max_speed_hz = 7629
		self.spi.mode = 0b01
		self.temperature = self.read()

	def read_32(self):
		"""
		Reads 32 bits from hardware SPI
		"""
		raw = self.spi.readbytes(4)
		if raw is None or len(raw) !=4:
			SmokeLog.common.error("SPI error, did not read expected number of bytes!")
		value = raw[0] << 24 | raw [1] << 16 | raw[2] << 8 | raw[3]
		return value

	def read_internal(self):
		"""
		Returns internal temp in degrees Celsius
		"""
		voltage = self.read_32()
		voltage >>= 4 # Ignore bottom 4 bits of thermocouple data
		internal = voltage & 0x7FF # Grab bottom 11 bits as internal temperature data
		if voltage & 0x800:
			internal -= 4096 # Negative value, take two's complement and compute with subtraction because Python is a little odd about handling signed/unsigned
		return internal * 0.0625 # Scale by 0.0625 degrees C per bit and return value

	def read(self):
		"""
		Returns thermocouple temp from specified read method and returns in degrees Fahrenheit
		"""
		if self.linear:
			temp = self.read_linearized_temp()
		else:
			temp = self.read_temp()

		if float(format((temp * 1.8), ".2f")) == 0.0:
			self.connected = False
		else:
			self.connected = True

		if self.connected:
			temp = float(format((temp * 1.8 + 32), ".1f")) # Convert C to F and round to 1 decimal places
			SmokeLog.common.info(f"MAX31855: {temp}F")
			return int(temp)
		return None

	def read_temp(self):
		"""
		Returns thermocouple temp in degrees Celsius
		"""
		voltage = self.read_32()

		if voltage & 0x7: # Check for error reading value
			self.connected = False
			return 0
		self.connected = True
		if voltage & 0x80000000: # Check if signed bit is set
			voltage >>= 18 # Ignore bottom 18 bits of data
			voltage -= 16384 # Negative value, take two's complement and compute with subtraction because Python is a little odd about handling signed/unsigned
		else:
			voltage >>= 18 # Positive value, just shift the bits to get the value
		temp = float(voltage * 0.25) # Scale by 0.25 degrees C per bit and return value

		return (temp)

	def read_state(self):
		"""
		Returns dictionary of hardware state and fault codes
		"""
		voltage = self.read_32()
		return {
			"openCircuit": (voltage & (1 << 0)) > 0,
			"shortGND": (voltage & (1 << 1)) > 0,
			"shortVCC": (voltage & (1 << 2)) > 0,
			"fault": (voltage & (1 << 16)) > 0
		}

	def read_linearized_temp(self):
		"""
		Return the NIST-linearized thermocouple temperature value in degrees celsius.
		See https://learn.adafruit.com/calibrating-sensors/maxim-31855-linearization for more info.
		"""
		voltage_thermocouple = (self.read_temp() - self.read_internal()) * 0.041276 # MAX31855 thermocouple voltage reading in mV
		temperature_cold_junction = self.read_internal() # MAX31855 cold junction voltage reading in mV
		voltage_cold_junction = (-0.176004136860E-01 +
			0.389212049750E-01  * temperature_cold_junction +
			0.185587700320E-04  * math.pow(temperature_cold_junction, 2.0) +
			-0.994575928740E-07 * math.pow(temperature_cold_junction, 3.0) +
			0.318409457190E-09  * math.pow(temperature_cold_junction, 4.0) +
			-0.560728448890E-12 * math.pow(temperature_cold_junction, 5.0) +
			0.560750590590E-15  * math.pow(temperature_cold_junction, 6.0) +
			-0.320207200030E-18 * math.pow(temperature_cold_junction, 7.0) +
			0.971511471520E-22  * math.pow(temperature_cold_junction, 8.0) +
			-0.121047212750E-25 * math.pow(temperature_cold_junction, 9.0) +
			0.118597600000E+00  * math.exp(-0.118343200000E-03 * math.pow((temperature_cold_junction-0.126968600000E+03), 2.0)))
		voltage_sum = voltage_thermocouple + voltage_cold_junction # Cold junction voltage + thermocouple voltage
		if voltage_thermocouple < 0: # Calculate corrected temperature reading based on coefficients for 3 different ranges
			b0 = 0.0000000E+00
			b1 = 2.5173462E+01
			b2 = -1.1662878E+00
			b3 = -1.0833638E+00
			b4 = -8.9773540E-01
			b5 = -3.7342377E-01
			b6 = -8.6632643E-02
			b7 = -1.0450598E-02
			b8 = -5.1920577E-04
			b9 = 0.0000000E+00
		elif voltage_thermocouple < 20.644:
			b0 = 0.000000E+00
			b1 = 2.508355E+01
			b2 = 7.860106E-02
			b3 = -2.503131E-01
			b4 = 8.315270E-02
			b5 = -1.228034E-02
			b6 = 9.804036E-04
			b7 = -4.413030E-05
			b8 = 1.057734E-06
			b9 = -1.052755E-08
		elif voltage_thermocouple < 54.886:
			b0 = -1.318058E+02
			b1 = 4.830222E+01
			b2 = -1.646031E+00
			b3 = 5.464731E-02
			b4 = -9.650715E-04
			b5 = 8.802193E-06
			b6 = -3.110810E-08
			b7 = 0.000000E+00
			b8 = 0.000000E+00
			b9 = 0.000000E+00
		else:
			SmokeLog.common.error("thermocouple voltage out of range!")
			return 0
		return (b0 +
			b1 * voltage_sum +
			b2 * pow(voltage_sum, 2.0) +
			b3 * pow(voltage_sum, 3.0) +
			b4 * pow(voltage_sum, 4.0) +
			b5 * pow(voltage_sum, 5.0) +
			b6 * pow(voltage_sum, 6.0) +
			b7 * pow(voltage_sum, 7.0) +
			b8 * pow(voltage_sum, 8.0) +
			b9 * pow(voltage_sum, 9.0))

	def close(self):
		"""
		Close hardware SPI device
		"""
		self.spi.close()

class MAX31865:
	"""
	MAX31865 RTD driver
	"""

	def __init__(self, chip_select):
		"""
		Initialize MAX31865 device with hardware SPI on specified chip-select pin
		"""
		self.chip_select = chip_select
		self.r_value = 1000
		self.r_reference = 4300
		self.A = 3.90830E-3
		self.B = -5.775E-7
		self.spi = spidev.SpiDev()
		self.spi.open(0, chip_select)
		self.spi.max_speed_hz = 7629
		self.spi.mode = 0b01
		self.config()
		self.temperature = self.read()

	def config(self):
		"""
		Config register map:
		  V_Bias (1 = On)
		  Conversion Mode (1 = Auto)
		  1-Shot (0 = Off)
		  3-Wire (0 = Off)
		  Fault Detection (0 = Off)
		  Fault Detection (0 = Off)
		  Clear Faults (1 = On)
		  50/60Hz (0 = 60 Hz)
		"""
		config = 0b11000010 # 0xC2
		self.spi.xfer2([0x80, config])
		time.sleep(0.25)

	def read(self):
		"""
		Returns RTD temperature in degrees Fahrenheit
		"""
		msb = self.spi.xfer2([0x01, 0x00])[1]
		lsb = self.spi.xfer2([0x02, 0x00])[1]

		if lsb & 0b00000001: # Check fault
			SmokeLog.common.error(f"fault detected on SPI {self.chip_select}")
			self.get_fault()

		adc_measured = ((msb<<8) + lsb)>>1 # Shift MSB up 8 bits, add to LSB, remove fault bit (last bit)
		r_measured = float(adc_measured * self.r_reference) / (2**15)

		try:
			temp = self.resistance_to_temp(r_measured)
			temp = float(format((temp * 1.8 + 32), ".1f")) # Convert C to F and round to 1 decimal places
		except: # pylint: disable=W0702
			temp = 0 # TODO: add actual error handling here and remove pylint override, this is a hack for bringup to return 0 when no RTD is present
		SmokeLog.common.info(f"MAX31865: {temp}F")
		return int(temp)

	def resistance_to_temp(self, r_measured):
		"""
		Converts measured RTD resistance into degrees Celsius
		"""
		A = self.A
		B = self.B
		temp = (-A + math.sqrt(A * A - 4 * B * (1 - r_measured / self.r_value))) / (2 * B)
		return temp

	def get_fault(self):
		"""
		Checks RTD status register for fault codes
		"""
		fault = self.spi.xfer2([0x07,0x00])[1]

		if fault & 0b10000000:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: RTD High Threshold")
		if fault & 0b01000000:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: RTD Low Threshold")
		if fault & 0b00100000:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: REFIN- > 0.85 x V_BIAS")
		if fault & 0b0001000:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: REFIN- < 0.85 x V_BIAS (FORCE- Open)")
		if fault & 0b00001000:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: RTDIN- < 0.85 x V_BIAS (FORCE- Open)")
		if fault & 0b00000100:
			SmokeLog.common.error(f"SPI {self.chip_select} fault: Overvoltage/undervoltage fault")

	def close(self):
		"""
		Close hardware SPI device
		"""
		self.spi.close()

if __name__ == "__main__":
	sys.exit("I am a module, not a script.")