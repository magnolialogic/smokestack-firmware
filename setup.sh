#!/usr/bin/env bash

/usr/bin/python3.9 -m venv /opt/smokestack-firmware/env
source /opt/smokestack-firmware/env/bin/activate
PYTHONPATH=/opt/smokestack-firmware/env/lib/python3.9/site-packages
python env/bin/easy_install pip wheel
python -m pip install -r requirements.txt
