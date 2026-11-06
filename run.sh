#!/usr/bin/env bash

# get the arguments passed to the script
args="$@"

# run the python script with sudo and pass the arguments
sudo "$(which python3)" "$args"


sudo "$(which python3)" test.py
sudo "$(which python3)" capture.py
sudo "$(which python3)" usb_video_lab.py capture --out captures/cold_start --seconds 40
sudo "$(which python3)" extract_idr.py captures/cold_start/bulk_if0_ep81.bin --out captures/cold_start/idr_segments