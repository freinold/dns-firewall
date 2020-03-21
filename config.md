# Basic configuration
## Install Raspbian (Lite)

## Disable Wifi and Bluetooth

Add these lines to /boot/config.txt
'''bash
# ADDITIONAL: Disable WIFI and BLUETOOTH
dtoverlay=disable-wifi
dtoverlay=disable-bt
'''
