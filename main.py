#!/usr/bin/env python3
import ipaddress
import logging
import os
import shutil
import subprocess

DHCPCD_CONF = "/home/fw/dns-firewall/dhcpcd.conf"
DIR = "/etc/dns-fw"
LOG_FILE = DIR + "/log"
FW_CONF = DIR + "/fw.conf"
APT_PACKAGES = ["bind9", "bind9utils", "dnsutils", "nmap"]

LOGO = '''\033[33m
  (         )  (         (     (    (         (  (       (      (     (     
  )\ )   ( /(  )\ )      )\ )  )\ ) )\ )      )\))(   '  )\     )\ )  )\ )  
 (()/(   )\())(()/(     (()/( (()/((()/( (  ((_)()\ )((((_)(   (()/( (()/(  \033[31m
 /(_)) ((_)\  /(_))     /(_)) /(_))/(_)))\  (_(())\_)())\ _ )\ /(_)) /(_)) 
 (_))_   _((_)(_))      (_))_|(_)) (_)) ((_) _()    \))\ _ /  (_))  (_))   \033[7m
  |   \ | \| |/ __| ___ | |_  |_ _|| _ \| __|\ \    / /  /_\   | |   | |    
  | |) || .` |\__ \|___|| __|  | | |   /| _|  \ \/\/ /  / _ \  | |__ | |__  
  |___/ |_|\_||___/     |_|   |___||_|_\|___|  \_/\_/  /_/ \_\ |____||____| \033[0m'''


def main() -> None:
    # TODO: print(LOGO)
    os.makedirs(DIR, exist_ok=True)
    configure_logs()
    # Check if dns-firewall is already installed
    is_installed: bool = os.path.isfile(FW_CONF)
    if not is_installed:
        logging.warning("Software not installed. Starting installation now.")
        install()


def configure_logs() -> None:
    if not os.path.isfile(LOG_FILE):
        os.mknod(LOG_FILE)
    # noinspection PyArgumentList
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        #filename=LOG_FILE,
        #filemode="w",
        format="{asctime} - {levelname:8}: {message}",
        level=logging.INFO,
        style="{"
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
        logging.error("Error installing required packages: {0} \nAborting now.".format(error.stderr))
        exit(-1)

    # GET SUBNET INFO
    logging.info("Gathering local subnet and router information.")
    try:
        output = _bash("ip route | grep 'default' | awk '{print $3, $7}'")
        config["router"], config["dynamic_ip"] = map(lambda x: ipaddress.ip_address(x), output.strip().split(" "))
        config["subnet"] = ipaddress.ip_network(_bash("ip route | grep -v 'default' | awk '{print $1}'").rstrip())
        logging.info("IP-Address: {0}, Router: {1}, Subnet: {2}"
                     .format(config["dynamic_ip"], config["router"], config["subnet"]))
    except subprocess.CalledProcessError as error:
        logging.error("Error getting required local network information: {0}\nAborting now.".format(error.stderr))
        exit(-1)

    # GET ACTIVE CLIENTS INFO
    logging.info("Scanning network for active clients to get a free address.")
    devices = []
    try:
        output = _bash("sudo nmap -sn -n {0} --exclude {1} | "
                       "grep 'scan report' | "
                       "awk '{{print $5}}'".format(config["subnet"], config["dynamic_ip"])).rstrip()
        devices = list(map(lambda x: ipaddress.ip_address(x), output.split("\n")))
    except subprocess.CalledProcessError as error:
        logging.error("Error scanning local network: {0}\nAborting now.".format(error.stderr))
        exit(-1)

    # CALCULATE STATIC IP
    # TODO:  set rules for address change (out of DHCPCD range)
    logging.info("Calculating for a static IP.")
    for host in config["subnet"].hosts():
        if host not in devices:
            config["static_ip"] = host
            break

    logging.info("Static IP calculated: {0}".format(config["static_ip"]))
    # SET STATIC IP
    logging.info("Changing to static IP address configuration.")
    shutil.copy2(DHCPCD_CONF, DHCPCD_CONF + ".original")
    logging.debug("Saved original dhcpcd configuration with suffix '.original'.")
    with open(DHCPCD_CONF, "a") as dhcpcd_conf:
        static_conf = "\n# Static IPv4 configuration for dns-firewall \n" \
                      "interface eth0 \n" \
                      "static ip_address={0} \n" \
                      "static routers={1} \n" \
                      "static domain_name_servers={0} \n".format(config["static_ip"], config["router"])
        dhcpcd_conf.write(static_conf)
    logging.debug("Appended static configuration in dhcpcd.conf file.")

    # TODO: Need reboot to get effective.


def _bash(cmd: str) -> str:
    logging.debug("Bash Command: {0}".format(cmd))
    output: str = subprocess.run(
        cmd,
        shell=True,
        check=True,
        executable="/bin/bash",
        capture_output=True,
        text=True
    ).stdout
    logging.debug("Command Output: {0}".format(output))
    return output


if __name__ == '__main__':
    main()
