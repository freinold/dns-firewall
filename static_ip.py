#!/usr/bin/env python3
import ipaddress
import json
import logging  # TODO: Handle logging from different modules.
import os.path
import shutil

import bash

DHCPCD_CONF = "/etc/dhcpcd.conf"  # TODO: Changed for tests!
DHCPCD_CONF_COPY = DHCPCD_CONF + ".original"
INFO_FILE = "/etc/dns-fw/static_ip.info.json"
NET_DIRECTORY = "/sys/class/net"

STATIC_DHCPCD_CONF = '''
# Static IPv4 configuration, provided by python3 script static_ip.py
interface eth0
static ip_address={0}
static routers={1}
static domain_name_servers={2}
'''


class Info:
    def __init__(self, filename=None):
        self.router: ipaddress.IPv4Address
        self.subnet: ipaddress.IPv4Network
        self.original_ip: ipaddress.IPv4Address
        self.original_resolver: ipaddress.IPv4Address
        self.static_ip: ipaddress.IPv4Address
        self.resolver: ipaddress.IPv4Address
        if filename is not None:
            with open(filename) as file:
                info = json.load(file)
            self.router = ipaddress.IPv4Address(info["router"])
            self.subnet = ipaddress.IPv4Network(info["subnet"])
            self.original_ip = ipaddress.IPv4Address(info["original_ip"])
            self.original_resolver = ipaddress.IPv4Address(info["original_resolver"])
            self.static_ip = ipaddress.IPv4Address(info["static_ip"])
            self.resolver = ipaddress.IPv4Address(info["resolver"])

    def save(self, filename):
        with open(filename, "w") as file:
            json.dump({
                "router": self.router.exploded,
                "subnet": self.subnet.exploded,
                "original_ip": self.original_ip.exploded,
                "original_resolver": self.original_resolver.exploded,
                "static_ip": self.static_ip.exploded,
                "resolver": self.resolver.exploded
            }, file)


class Error(Exception):
    pass


def configure(use_info=False, self_as_resolver=False) -> None:
    # noinspection PyArgumentList
    logging.basicConfig(
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        format="{asctime} - {levelname:8}: {message}",
        level=logging.DEBUG,
        style="{"
    )
    if is_configured():
        return
    if use_info:
        info = Info(filename=INFO_FILE)
    else:
        info = Info()
        # GET SUBNET INFO
        logging.info("Gathering local subnet and router information.")
        try:
            info.router = ipaddress.IPv4Address(bash.call("ip route | "
                                                          "grep 'default' | "
                                                          "grep 'eth0' | "
                                                          "awk '{print $3}'").strip())
            info.original_ip = ipaddress.IPv4Address(bash.call("ip addr show dev eth0 | "
                                                               "grep 'inet ' | "
                                                               "awk '{ print $2 }'").split("/")[0])
            info.subnet = ipaddress.IPv4Network(bash.call("ip route | "
                                                          "grep -v 'default' | "
                                                          "awk '{print $1}'").rstrip())
            info.original_resolver = ipaddress.IPv4Address(bash.call("cat /etc/resolv.conf | "
                                                                     "grep -m 1 'nameserver' | "
                                                                     "awk '{print $2}'").rstrip())
        except bash.CallError as error:
            logging.critical(
                "Critical error getting required local network information: {0}\n"
                "Aborting now.".format(error))
            exit(-1)
        finally:
            logging.info("Gathered information:\n"
                         "IP-Address: {info.original_ip},\n"
                         "Router: {info.router},\n"
                         "Subnet: {info.subnet},\n"
                         "Resolver: {info.original_resolver}".format(info=info))

        # GET ACTIVE CLIENTS INFO
        logging.info("Scanning network for active host to get used addresses.")
        devices = []
        try:
            output = bash.call("sudo nmap -sn -n {0} --exclude {1} | "
                               "grep 'scan report' | "
                               "awk '{{print $5}}'".format(info.subnet, info.original_ip)).rstrip()
            devices = list(map(lambda x: ipaddress.IPv4Address(x), output.split("\n")))
        except bash.CallError as error:
            logging.error("Error scanning local network: {0}\n"
                          "Errors configuring static IP are possible.".format(error))
            devices.append(info.router)
        finally:
            logging.info("{0} active clients found.".format(len(devices)))

        # SELECT STATIC IP
        # TODO: Try to get DHCP range to be sure.
        logging.info("Selecting an unused static IP.")
        for host in info.subnet.hosts():
            if host not in devices:
                info.static_ip = host
                break
        logging.info("Static IP selected: {0}".format(info.static_ip))

        # CHOOSE RESOLVER
        info.resolver = info.static_ip if self_as_resolver else info.original_resolver

        # WRITE INFO TO FILE FOR OTHERS TO USE
        info.save(INFO_FILE)

    # SET STATIC IP
    logging.info("Changing DHCP Client Daemon to static IP address configuration.")
    shutil.copy2(DHCPCD_CONF, DHCPCD_CONF + ".original")
    logging.debug("Saved original dhcpcd.conf with suffix '.original'.")
    with open(DHCPCD_CONF, "a") as dhcpcd_conf:
        static_conf = STATIC_DHCPCD_CONF.format(info.static_ip,
                                                info.router,
                                                info.resolver)
        dhcpcd_conf.write(static_conf)
    logging.debug("Appended static configuration to dhcpcd.conf file.")

    # REBOOT_NETWORK
    try:
        _reboot_network()
    except bash.CallError as error:
        shutil.move(DHCPCD_CONF_COPY, DHCPCD_CONF)
        raise Error("Error raised while restarting with the new configuration:\n"
                    "{0}\n"
                    "Please try again or restart services dhcpcd and networking yourself.")


def is_info() -> bool:
    return os.path.isfile(INFO_FILE)


def is_configured() -> bool:
    with open(DHCPCD_CONF) as dhcpcd_conf:
        lines = dhcpcd_conf.readlines()
    for line in lines:
        if "static ip_address=" in line and not line.strip().startswith("#"):
            return True
    return False


def revert() -> None:
    if not is_configured():
        return
    if os.path.isfile(DHCPCD_CONF_COPY):
        shutil.copy2(DHCPCD_CONF_COPY, DHCPCD_CONF)
        try:
            _reboot_network()
        except bash.CallError as error:
            raise Error("Error raised while restarting with the original configuration:\n"
                        "{0}\n"
                        "Please try again or restart services dhcpcd and networking yourself.".format(error))
        finally:
            os.remove(DHCPCD_CONF_COPY)
            os.remove(INFO_FILE)
    else:
        # NEED TO REMOVE LINES ONE BY ONE WHILE READING THROUGH THEM
        statements = ["interface ", "static ip_address=", "static routers=", "static domain_name_servers="]
        with open(DHCPCD_CONF) as file:
            dhcpcd_conf = file.readlines()

        dynamic_dhcpcd_conf = []
        for line in dhcpcd_conf:
            part_of_static_config = False
            for statement in statements:
                if statement in line and not line.lstrip().startswith("#"):
                    part_of_static_config = True
            if not part_of_static_config:
                dynamic_dhcpcd_conf.append(line)

        with open(DHCPCD_CONF, "w") as file:
            file.writelines(dynamic_dhcpcd_conf)


def _reboot_network() -> None:  # Can raise bash.CallError
    bash.call("sudo systemctl daemon-reload")
    bash.call("sudo systemctl stop dhcpcd")
    for device in os.listdir(NET_DIRECTORY):
        bash.call("sudo ip addr flush dev {0}".format(device))
    bash.call("sudo systemctl start dhcpcd")
    bash.call("sudo systemctl restart networking")
