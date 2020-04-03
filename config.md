  ```console
  fw@dns-firewall:~ $ 
  ```
# Basic configuration
## Hardware
Raspberry Pi 4 (2GB?), SD Card (TODO: Size?) and Raspberry Pi PoE Hat
## Install Raspbian (Lite)
Transfer image to SD Card
## Disable Wifi and Bluetooth
- Open `config.txt` on the `Boot` Partition of the SD Card and add these lines at the bottom of the file:
  ```bash
  # Disable wifi and bluetooth
  dtoverlay=disable-wifi
  dtoverlay=disable-bt
  ```
## Start up
- Connect Raspberry Pi to Router by Ethernet Cable
- (Connect Raspberry Pi to Power Cable)
- Get IP Adress from Router Interface
- Login via SSH: Standard User is `pi`; Password is `raspberry`
## Check internet connection
- Try to ping Google:
  ```console
  pi@raspberry:~ $ ping www.google.com
  ```
## Update and upgrade software
- Update package lists:
  ```console
  pi@raspberry:~ $ sudo apt update
  ```
- Upgrade packages:
  ```console
  pi@raspberry:~ $ sudo apt full-upgrade
  ```
- Remove old packages: 
  ```console
  pi@raspberry:~ $ sudo apt autoremove
  ```
## First configurations via raspi-config
- Launch raspi-config:
  ```console
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
  ```console
  pi@dns-firewall:~ $ 
  ```
## Change user
- Add new user `fw` and grant him sudo privileges:
  ```console
  pi@dns-firewall:~ $ sudo adduser fw # Passwort prompt will open
  pi@dns-firewall:~ $ sudo adduser fw sudo
  ```
- Log out as `pi` and log in as `fw`:
  ```console
  pi@dns-firewall:~ $ exit
  login as: fw
  fw's password:
  fw@dns-firewall:~ $ 
  ```
- Delete user `pi`:
  ```console
  fw@dns-firewall:~ $ sudo userdel -r pi
  ```
## Install necessary packages
```console
fw@dns-firewall:~ $ sudo apt update
fw@dns-firewall:~ $ sudo apt install bind9 bind9-doc bind9utils dnsutils -y
```
