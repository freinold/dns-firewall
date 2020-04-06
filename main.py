#!/usr/bin/env python3
import logging
import shutil
import subprocess
import os

logging.basicConfig(filename="/etc/dns-fw/log")


def main() -> None:
    # Check if dns-firewall is already installed
    if not os.path.isdir("/etc/dns-fw"):
        install()


def install():
    # Get BIND9 and supporting packages.
    try:
        _bash("sudo apt update")
        _bash("sudo apt install bind9 bind9utils dnsutils -y")
    except subprocess.CalledProcessError:
        logging.critical("Error installing required BIND9 packages, aborting now.")
        exit(-1)
    # Get local subnet and router
    try:
        cp = _bash("ip addr show eth0 | grep 'inet ' | awk '{print $2}'")
        current_ip, router = cp.stdout.split(" ")
        print(current_ip, router)
        cp = _bash("ip route")
    except subprocess.CalledProcessError:
        logging.critical("Error getting required local network information, aborting now.")
        exit(-1)
    exit(0)
    # Set static IP address.
    shutil.copy2("/etc/dhcpcd.conf", "/etc/dhcpcd.conf.original") # Copy original dhcpcd configuration.
    with open("/etc/dhcpcd.conf", "a") as dhcpcd_conf:
        static_conf = "# Static IPv4 configuration for dns-firewall \n" \
                      "interface eth0 \n" \
                      "static ip_address=192.168.178.2 \n" \
                      "static routers=192.168.178.1 \n" \
                      "static domain_name_servers=192.168.178.2 \n"
        dhcpcd_conf.write(static_conf)
    # Need reboot to get effective.


def _bash(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=True, executable="/bin/bash", capture_output=True)


if __name__ == '__main__':
    main()