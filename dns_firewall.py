#!/usr/bin/env python3
import logging
import os
import subprocess
import time

import bash
import static_ip

APT_PACKAGES = ["bind9", "bind9utils", "dnsutils", "nmap"]

DIR = "/etc/dns-fw"
LOG = DIR + "/log"
FW_CONF = DIR + "/fw.conf"

BIND_DIR = "/etc/bind"
NAMED_CONF = BIND_DIR + "/named.conf"
NAMED_CONF_OPTIONS = BIND_DIR + "/named.conf.options"
NAMED_CONF_LOCAL = BIND_DIR + "/named.conf.local"

LOGO = '''\033[33m
  (         )  (         (     (    (         (  (       (      (     (     
  )\ )   ( /(  )\ )      )\ )  )\ ) )\ )      )\))(   '  )\     )\ )  )\ )  
 (()/(   )\())(()/(     (()/( (()/((()/( (  ((_)()\ )((((_)(   (()/( (()/(  \033[31m
 /(_)) ((_)\  /(_))     /(_)) /(_))/(_)))\  (_(())\_)())\ _ )\ /(_)) /(_)) 
 (_))_   _((_)(_))      (_))_|(_)) (_)) ((_) _()    \))\ _ /  (_))  (_))   \033[7m
  |   \ | \| |/ __| ___ | |_  |_ _|| _ \| __|\ \    / /  /_\   | |   | |    
  | |) || .` |\__ \|___|| __|  | | |   /| _|  \ \/\/ /  / _ \  | |__ | |__  
  |___/ |_|\_||___/     |_|   |___||_|_\|___|  \_/\_/  /_/ \_\ |____||____| \033[0m'''

CUSTOM_BIND_CONFIG='''

'''

ZONE_LOCAL='''
zone "{0}" IN {
        type forward;
        forwarders { {1}; };
        forward only;
'''


def main() -> None:
    # print(LOGO)
    os.makedirs(DIR, exist_ok=True)
    configure_logs()
    # Check if dns-firewall is already installed
    is_installed: bool = os.path.isfile(FW_CONF)
    if not is_installed:
        logging.warning("Software not installed. Starting installation now.")
        install()


def configure_logs() -> None:
    if not os.path.isfile(LOG):
        os.mknod(LOG)
    # noinspection PyArgumentList
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        # filename=LOG_FILE,
        # filemode="w",
        format="{asctime} - {levelname:8}: {message}",
        level=logging.INFO,
        style="{"
    )
    logging.info("DNS-FIREWALL started.")


def install() -> None:
    # DOWNLOAD PACKAGES
    logging.info("Downloading all required packages.")
    try:
        bash.call("sudo apt update")
        bash.call("sudo apt install {0} -y".format(" ".join(APT_PACKAGES)))
    except subprocess.CalledProcessError as error:
        logging.critical("Critical error installing required packages: {0} \nAborting now.".format(error.stderr))
        exit(-1)
    finally:
        logging.info("All required packages downloaded.")

    # CONFIGURE STATIC IP
    if not static_ip.is_configured():
        static_ip.configure()
        time.sleep(10)
    else:
        info = static_ip.get_info()
        if info["resolver"] != info["static_ip"]:
            static_ip.revert()
            time.sleep(10)
            static_ip.configure(use_info=True, self_as_resolver=True)
            time.sleep(10)
    info = static_ip.get_info()

    # QUERY OLD RESOLVER FOR NAME OF ROUTER
    try:
        router_name = bash.call("sudo nmap -sn -R {0} --dns-servers {1} | "
                                "grep 'scan report' | "
                                "awk '{{print $5}}'".format(info["router"], info["original_resolver"]))
    except bash.CallError as error:
        logging.error("Error: Could not retrieve routers name from original resolver. Access via domain not possible.")
        router_name = ""

    # ADD CUSTOM BIND CONFIGURATION
    with open(NAMED_CONF_OPTIONS, "w") as named_conf_options:
        named_conf_options.write(CUSTOM_BIND_CONFIG.format(info["subnet"]))

    # USE OLD RESOLVER (MOST PROBABLY ROUTER) TO RESOLVE LOCAL SUBNET
    if len(router_name) > 0:
        with open(NAMED_CONF_LOCAL, "w") as named_conf_local:
            named_conf_local.write(ZONE_LOCAL.format(router_name, info["original_resolver"]))

    # CHECK CONFIGURATION
    try:
        output = bash.call("sudo named-checkconf -f {0}".format(NAMED_CONF))
        if output != "":
            logging.critical("BIND9 config is corrupted:\n"
                             "{0}\n"
                             "Aborting now.".format(output))
            exit(-1)
    except bash.CallError as error:
        logging.critical("Error thrown while checking BIND9 config:\n"
                         "{0}\n"
                         "Aborting now.".format(error))

    # RESTART BIND
    try:
        bash.call("sudo service bind9 restart")
    except bash.CallError as error:
        logging.critical("Error thrown while restarting BIND9 with new config:\n"
                         "{0}\n"
                         "Aborting now.".format(error))
        exit(-1)


def load() -> None:
    # UPDATE PACKAGES
    logging.info("Updating necessary packages.")
    try:
        bash.call("sudo apt update")
        bash.call("sudo apt upgrade")
    except subprocess.CalledProcessError as error:
        logging.error("Error updating packages: {0}\nIf used packages are outdated, there could be vulnerabilities.")
    finally:
        logging.info("Package update finished.")

    # LOAD NAMED CONFIG
    # TODO: Implement loading of config from server / pre loaded files.
    # RESTART BIND9
    logging.info("Restarting BIND9 for changes to take effect.")
    attempts = 3
    try:
        for x in range(attempts):
            bash.call("sudo systemctl restart bind9")
            output = bash.call("sudo systemctl bind9 is-active").rstrip()
            if output == "active":
                break
        else:
            raise subprocess.CalledProcessError(
                cmd="sudo systemctl restart bind9",
                returncode=-1,
                stderr="BIND9 is not active after after {0} restart attempts".format(attempts)
            )
    except subprocess.CalledProcessError as error:
        logging.critical("Critical error restarting BIND9: {0}\nAborting now.".format(error.stderr))
        exit(-1)
    finally:
        logging.info("BIND9 restarted successfully.")


if __name__ == '__main__':
    main()
