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
# Static IPv4 configuration for dns-firewall
interface eth0
static ip_address={0}
static routers={1}
static domain_name_servers={2}
'''


class Error(Exception):
    pass


def configure(use_info=False, self_as_resolver=False) -> None:
    if is_configured():
        return
    if use_info:
        with open(INFO_FILE) as config_file:
            info = json.load(config_file)
        if len(info) == 0:
            raise Error("Error using info: Info file is empty. Please try again without parameter.")
    else:
        info = {}
        # GET SUBNET INFO
        logging.info("Gathering local subnet and router information.")
        try:
            output = bash.call("ip route | "
                               "grep 'default' | "
                               "awk '{print $3, $7}'")
            info["router"], info["original_ip"] = map(lambda x: ipaddress.ip_address(x), output.strip().split(" "))
            info["subnet"] = ipaddress.ip_network(bash.call("ip route | "
                                                            "grep -v 'default' | "
                                                            "awk '{print $1}'").rstrip())
            info["original_resolver"] = ipaddress.ip_address(bash.call("cat /etc/resolv.conf | "
                                                                       "grep -m 1 'nameserver' | "
                                                                       "awk '{print $2}'").rstrip())
        except bash.CallError as error:
            logging.critical(
                "Critical error getting required local network information: {0}\n"
                "Aborting now.".format(error))
            exit(-1)
        finally:
            logging.info("Gathered information:\n"
                         "IP-Address: {original_ip},\n"
                         "Router: {router},\n"
                         "Subnet: {subnet},\n"
                         "Resolver: {original_resolver}".format(**info))

        # GET ACTIVE CLIENTS INFO
        logging.info("Scanning network for active host to get used addresses.")
        devices = []
        try:
            output = bash.call("sudo nmap -sn -n {0} --exclude {1} | "
                               "grep 'scan report' | "
                               "awk '{{print $5}}'".format(info["subnet"], info["original_ip"])).rstrip()
            devices = list(map(lambda x: ipaddress.ip_address(x), output.split("\n")))
        except bash.CallError as error:
            logging.error("Error scanning local network: {0}\n"
                          "Errors configuring static IP are possible.".format(error))
            devices.append(info["router"])
        finally:
            logging.info("{0} active clients found.".format(len(devices)))

        # SELECT STATIC IP
        # TODO: Try to get DHCP range to be sure.
        logging.info("Selecting an unused static IP.")
        for host in info["subnet"].hosts():
            if host not in devices:
                info["static_ip"] = host
                break
        logging.info("Static IP selected: {0}".format(info["static_ip"]))

        # CHOOSE RESOLVER
        info["resolver"] = info["static_ip"] if self_as_resolver else info["original_resolver"]

        # WRITE INFO TO FILE FOR OTHERS TO USE
        for key, item in info.items():
            info[key] = item.exploded
        with open(INFO_FILE, "w") as info_file:
            json.dump(info, info_file)

    # SET STATIC IP
    logging.info("Changing DHCP Client Daemon to static IP address configuration.")
    shutil.copy2(DHCPCD_CONF, DHCPCD_CONF + ".original")
    logging.debug("Saved original dhcpcd.conf with suffix '.original'.")
    with open(DHCPCD_CONF, "a") as dhcpcd_conf:
        static_conf = STATIC_DHCPCD_CONF.format(info["static_ip"],
                                                info["router"],
                                                info["resolver"])
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


def get_info() -> dict:
    if os.path.isfile(INFO_FILE):
        with open(INFO_FILE) as info_file:
            return json.load(info_file)
    else:
        return {}


def is_configured() -> bool:
    with open(DHCPCD_CONF) as dhcpcd_conf:
        lines = dhcpcd_conf.readlines()
    for line in lines:
        if "static static ip_address=" in line and not line.strip().startswith("#"):
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
        raise Error("Error: No dhcpcd.conf.original file found to revert to.")


def _reboot_network() -> None:  # Can raise bash.CallError
    bash.call("sudo systemctl daemon-reload")
    bash.call("sudo systemctl stop dhcpcd")
    for device in os.listdir(NET_DIRECTORY):
        bash.call("sudo ip addr flush dev {0}".format(device))
    bash.call("sudo systemctl start dhcpcd")
    bash.call("sudo systemctl restart networking")
