# Basic configuration
## Install Raspbian (Lite) 
### raspi-config:
expand filesystem &
activate wait for network while booting
## Change user
- Add new user `fw` and grant him sudo privileges:
  ```bash
  pi@raspberry:~ $ sudo adduser fw # Passwort prompt will open
  pi@raspberry:~ $ sudo adduser fw sudo
  ```
- Log out as `pi` and log in as `fw`:
  ```bash
  pi@raspberry:~ $ exit
  login as: fw
  fw's password:
  fw@raspberry:~ $ 
  ```
- Delete user `pi`:
  ```bash
  fw@raspberry:~ $ sudo userdel -r pi
  ```
- Change Hostname:
  ```bash
  fw@raspberry:~ $ sudo raspi-config
  ```
  Pick `2 Network Options` and next `N1 Hostname`.
  
  Enter new hostname "dns-firewall" and click `Enter`.
  
  Exit raspi-config by clicking `Finish`.
  
  Confirm reboot by chossing `<Yes>` and log back in afterwards:
  ```bash
  fw@dns-firewall:~ $ 
  ```

## Disable Wifi and Bluetooth
- Add these lines at the bottom of `/boot/config.txt`:
  ```bash
  # ADDITIONAL: Disable WIFI and BLUETOOTH
  dtoverlay=disable-wifi
  dtoverlay=disable-bt
  ```
