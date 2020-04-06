#!/usr/bin/env python3
import logging
import shutil
import subprocess
import os


def main() -> None:
    is_installed: bool = os.path.isdir("/etc/dns-fw")
    configure_logs(is_installed)
    # Check if dns-firewall is already installed
    if not is_installed:
        logging.info("Software not installed. Starting installation now.")
        install()


def configure_logs(is_installed: bool) -> None:
    if not is_installed:
        os.mkdir("/etc/dns-fw")
        os.mknod("/etc/dns-fw/log")
    logging.basicConfig(filename="/etc/dns-fw/log", level=logging.INFO)
    logging.info("Logging is set up.")


def install() -> None:
    logging.info("Getting BIND9 and supporting packages.")
    try:
        _bash("sudo apt update")
        _bash("sudo apt install bind9 bind9utils dnsutils -y")
    except subprocess.CalledProcessError:
        logging.critical("Error installing required BIND9 packages, aborting now.")
        exit(-1)
    # Get local subnet and router
    try:
        cp = _bash("ip route | grep 'default' | awk '{print $3, $7}'")
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
    return subprocess.run(cmd, shell=True, check=True, executable="/bin/bash", capture_output=True, text=True)


if __name__ == '__main__':
    main()
