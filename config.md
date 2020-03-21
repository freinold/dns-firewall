  ```bash
  pi@raspberry:~ $ 
  ```
# Basic configuration
## Hardware
Raspberry Pi 4 and PoE Hat
## Install Raspbian (Lite)
Transfer image to SD
## Start Raspberry
- Connect to Router by Ethernet Cable
- Connect Raspberry Pi to Power
- Get IP Adress from Router Interface
- Login via SSH: Standard User is `pi`; Password is `raspberry`
## Check internet connection
- Try to ping Google:
  ```bash
  pi@raspberry:~ $ ping www.google.com
  ```
## Update and upgrade software
- Update package lists:
  ```bash
  pi@raspberry:~ $ sudo apt update
  ```
- Upgrade packages:
  ```bash
  pi@raspberry:~ $ sudo apt full-upgrade
  ```
- Remove old packages: 
  ```bash
  pi@raspberry:~ $ sudo apt autoremove
  ```
## First configurations via raspi-config
- Launch raspi-config:
  ```bash
  pi@raspberry:~ $ sudo raspi-config
  ```
- Change Hostname:  
  Pick `2 Network Options` and next `N1 Hostname`  
  Enter new hostname "dns-firewall" and click `Enter`.
- Wait for Network at Boot:  
  Pick `3 Boot Options` and next `B2 Wait for Network at Boot`, where you choose `<Yes>`
- Expand Filesystem:  
  Pick `7 Advanced Options` and next `A1 Expand Filesystem`.
- Exit raspi-config:  
  Pick `<Finish>` in the main menu.  
  Confirm reboot by chossing `<Yes>`.  
  When you log back in afterwards, the hostname in the console should have changed: 
  ```bash
  pi@dns-firewall:~ $ 
  ```
## Change user
- Add new user `fw` and grant him sudo privileges:
  ```bash
  pi@dns-firewall:~ $ sudo adduser fw # Passwort prompt will open
  pi@dns-firewall:~ $ sudo adduser fw sudo
  ```
- Log out as `pi` and log in as `fw`:
  ```bash
  pi@dns-firewall:~ $ exit
  login as: fw
  fw's password:
  fw@dns-firewall:~ $ 
  ```
- Delete user `pi`:
  ```bash
  fw@dns-firewall:~ $ sudo userdel -r pi
  ```
## Disable Wifi and Bluetooth
- Add these lines at the bottom of `/boot/config.txt`:
  ```bash
  fw@dns-firewall:~ $ sudo nano /boot/config.txt
  ```
  ```bash
  # ADDITIONAL: Disable WIFI and BLUETOOTH
  dtoverlay=disable-wifi
  dtoverlay=disable-bt
  ```
