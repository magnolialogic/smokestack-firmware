# smokestack-firmware
Python smoker controller firmware for Raspberry Pi

Uses [smokestack-vapor](https://github.com/magnolialogic/smokestack-vapor) to interact with [smokestack-app](https://github.com/magnolialogic/smokestack-app)

### System Requirements
* Raspberry Pi 3B+ and [smokestack-hw](https://github.com/magnolialogic/smokestack-hw)
* Ubuntu@20.04.3 ([needs to be updated to work with 21.04+ kernel](https://ubuntu.com/tutorials/gpio-on-raspberry-pi#1-overview))
* Python@3.9.5

### Installation
0. As a sudoer, install apt dependencies and create a sudo user for the systemd job (yes I know this sucks but it's necessary for GPIO access)
   a. `sudo apt install rpi.gpio-common python3.9-dev`
   b. `sudo useradd --user-group --no-create-home --home-dir /opt/smokestack-firmware --groups sudo --shell /bin/bash --password "" smokestack`
1. Clone repository into /opt/smokestack-firmware
2. `bash /opt/smokestack-firmware/setup.sh`
3. Create a copy of etc/config.yml in /opt/smokestack-firmware, edit with your [smokestack-vapor](https://github.com/magnolialogic/smokestack-vapor) URL and secret key
4. Install systemd service file: `sudo ln -s /opt/smokestack-firmware/Smokestack.service /etc/systemd/system/Smokestack.service`
5. Enable and start systemd service: `sudo systemctl enable Smokestack.service && sudo systemctl start Smokestack.service`
