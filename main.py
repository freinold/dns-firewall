#!/usr/bin/env python3
import logging
import os
import shutil
import subprocess

DHCPCD_CONF = "/etc/dhcpcd.conf"
DIR = "/etc/dns-fw"
LOG_FILE = DIR + "/log"
FW_CONF = DIR + "/fw.conf"
APT_PACKAGES = ["bind9", "bind9utils", "dnsutils", "nmap"]

LOGO = '''\033[33m
  (         )  (         (     (    (                           (     (     
  )\ )   ( /(  )\ )      )\ )  )\ ) )\ )      (  (       (      )\ )  )\ )  
 (()/(   )\())(()/(     (()/( (()/((()/( (    )\))(   '  )\    (()/( (()/(  
\033[91m  /(_)) ((_)\  /(_))     /(_)) /(_))/(_)))\ \033[33m ((_)()\ )((((_)( \033[91m  /(_)) /(_)) 
 (_))_   _((_)(_))      (_))_|(_)) (_)) ((_) _(())\_)())\ _ )\ (_))  (_))   \033[31m
  |   \ | \| |/ __| ___ | |_  |_ _|| _ \| __|\ \\\033[91m((_)\033[31m/ /\033[91m(_)\033[31m_\\\033[91m(_)\033[31m| |   | |    
  | |) || .` |\__ \|___|| __|  | | |   /| _|  \ \/\/ /  / _ \  | |__ | |__  
  |___/ |_|\_||___/     |_|   |___||_|_\|___|  \_/\_/  /_/ \_\ |____||____| 
  \033[0m'''


def main() -> None:
    print(LOGO)
    # Check if dns-firewall is already installed
    is_installed: bool = os.path.isfile(FW_CONF)
    configure_logs(is_installed)
    if not is_installed:
        logging.warning("Software not installed. Starting installation now.")
        install()


def configure_logs(is_installed: bool) -> None:
    if not is_installed:
        os.makedirs("/etc/dns-fw", exist_ok=True)
        os.mknod(LOG_FILE)
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        filename=LOG_FILE,
        format="%(asctime)s - %(levelname)s: %(message)s",
        level=logging.DEBUG,
    )
    logging.info("DNS-FIREWALL started.")


def install() -> None:
    config = {}
    # DOWNLOAD PACKAGES
    logging.info("Downloading all required packages.")
    try:
        _bash("sudo apt update")
        _bash("sudo apt install {0} -y".format(" ".join(APT_PACKAGES)))
    except subprocess.CalledProcessError as error:
        logging.error("Error installing required packages: %s \nAborting now.", error.stderr)
        exit(-1)

    # GET SUBNET INFO
    logging.info("Gathering local subnet and router information.")
    try:
        output = _bash("ip route | "
                       "grep 'default' | "
                       "awk '{print $3, $7}'")
        config.dynamic_ip, config.router = output.split(" ")
        config.subnet = _bash("ip route | "
                              "grep -v 'default' | "
                              "awk '{print $1}'")
        logging.info("IP-Address: %s, Router: %s, Subnet: %s", config.dynamic_ip, config.router, config.subnet)
    except subprocess.CalledProcessError as error:
        logging.error("Error getting required local network information: %s\nAborting now.", error.stderr)
        exit(-1)

    # GET ACTIVE CLIENTS INFO
    logging.info("Scanning network for active clients to get a free address.")
    try:
        output = _bash("sudo nmap -sn -n 192.168.178.0/24 --exclude 192.168.178.2 | "
                       "grep 'scan report' | "
                       "awk '{print $5}'")
    except subprocess.CalledProcessError as error:
        logging.error("Error scanning local network: %s\nAborting now.", error.stderr)
        exit(-1)

    # STATIC IP
    logging.info("Changing to static IP address configuration.")
    # TODO: Scan with nmap and set rules for address change (out of DHCPCD range)
    config.static_ip = config.dynamic_ip
    shutil.copy2(DHCPCD_CONF, DHCPCD_CONF + ".original")
    logging.debug("Saved original dhcpcd configuration with suffix '.original'.")
    with open(DHCPCD_CONF, "a") as dhcpcd_conf:
        static_conf = "# Static IPv4 configuration for dns-firewall \n" \
                      "interface eth0 \n" \
                      "static ip_address={0} \n" \
                      "static routers={1} \n" \
                      "static domain_name_servers={0} \n".format(config.static_ip, config.router)
        dhcpcd_conf.write(static_conf)
    logging.debug("Appended static configuration in dhcpcd.conf file.")

    # TODO: Need reboot to get effective.


def _bash(cmd: str) -> str:
    logging.debug("Bash Command: %s", cmd)
    output = subprocess.run(
        cmd,
        shell=True,
        check=True,
        executable="/bin/bash",
        capture_output=True,
        text=True
    ).stdout
    logging.debug("Command Output: %s", output)
    return output


if __name__ == '__main__':
    main()
