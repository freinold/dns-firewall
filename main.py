#!/usr/bin/env python3
import datetime
import logging
import os
import shutil
import signal

import time

import bash
import static_ip

# import pi_baseclient.bash as bash
# import pi_baseclient.static_ip as static_ip

APT_PACKAGES = ["bind9", "bind9utils", "dnsutils", "nmap"]

DIR = "/etc/dns-fw/"
LOG_FILE = "/etc/dns-fw/log"
FW_CONF = DIR + "/etc/dns-fw/fw.conf.json"
FW_IS_INSTALLED = "/etc/dns-fw/installed"
CUSTOM_NAMED_CONF = "/etc/dns-fw/named.conf"

BIND_DIR = "/etc/bind/"
NAMED_CONF = "/etc/bind/named.conf"
DOT_CONF = "/etc/stunnel/dot.conf"

BLANK_DOT_CONF = "resources/dot.conf"
BLANK_NAMED_CONF = "resources/named.conf"
ZONE_TEMPLATE = "resources/zone_template"
SERVER_TEMPLATE = "resources/server_template"
RPZ_HEADER_TEMPLATE = "resources/rpz_header_template"

LOGO = '''\033[33m
  (         )  (         (     (    (         (  (       (      (     (     
  )\ )   ( /(  )\ )      )\ )  )\ ) )\ )      )\))(   '  )\     )\ )  )\ )  
 (()/(   )\())(()/(     (()/( (()/((()/( (  ((_)()\ )((((_)(   (()/( (()/(  \033[31m
 /(_)) ((_)\  /(_))     /(_)) /(_))/(_)))\  (_(())\_)())\ _ )\ /(_)) /(_)) 
 (_))_   _((_)(_))      (_))_|(_)) (_)) ((_) _()    \))\ _ /  (_))  (_))   \033[7m
  |   \ | \| |/ __| ___ | |_  |_ _|| _ \| __|\ \    / /  /_\   | |   | |    
  | |) || .` |\__ \|___|| __|  | | |   /| _|  \ \/\/ /  / _ \  | |__ | |__  
  |___/ |_|\_||___/     |_|   |___||_|_\|___|  \_/\_/  /_/ \_\ |____||____| \033[0m
'''


def main() -> None:
    """Main function used if script is called directly."""
    print(LOGO)
    make_directory()
    configure_logs(interactive=True)
    # Check if dns_firewall is already installed
    is_installed: bool = os.path.isfile(FW_IS_INSTALLED)
    if not is_installed:
        logging.warning("Software not installed. Starting installation now.")
        install()


def run() -> None:
    """Main function used if called as an app."""
    signal.signal(signal.SIGTERM, _sigterm_handler)
    make_directory()
    configure_logs(interactive=False)
    # TODO: Further calls like in main().


def make_directory() -> None:
    """Creates own subdirectory in /etc/."""
    if not os.path.isdir(DIR):
        os.makedirs(DIR, exist_ok=True)


def configure_logs(interactive: bool = False) -> None:
    """Configures logging to own log file."""
    if interactive:
        # noinspection PyArgumentList
        logging.basicConfig(
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            format="{asctime} - {levelname:8}: {message}",
            level=logging.DEBUG,
            style="{"
        )
    else:
        if not os.path.isfile(LOG_FILE):
            os.mknod(LOG_FILE)
        # noinspection PyArgumentList
        logging.basicConfig(
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            filename=LOG_FILE,
            filemode="a",
            format="{asctime} - {levelname:8}: {message}",
            level=logging.INFO,
            style="{"
        )
        logging.info("DNS-FIREWALL started.")


def install() -> None:
    """Installs the dependencies, sets static ip and builds general custom BIND9 configuration."""
    # DOWNLOAD PACKAGES (WILL BE DONE BY APP-CONTROLLER)
    logging.info("Downloading all required packages.")
    with open("apt_packages") as file:
        apt_packages = file.readlines()
    apt_packages = list(map(lambda x: x.strip(), apt_packages))
    try:
        bash.call("sudo apt update")
        bash.call("sudo apt install {0} -y".format(" ".join(apt_packages)))
    except bash.CallError as error:
        logging.critical("Critical error installing required packages:\n"
                         "{0}\n"
                         "Aborting now.".format(error))
        exit(-1)
    finally:
        logging.info("All required packages downloaded.")

    # CONFIGURE STATIC IP
    if not static_ip.is_configured():
        static_ip.configure(self_as_resolver=True)
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

    # BUILD CUSTOM BIND CONFIGURATION
    with open(BLANK_NAMED_CONF) as file:
        custom_named_conf = file.read()
        custom_named_conf = custom_named_conf.replace("{SUBNET}", info["subnet"])
        if len(router_name) > 0:
            custom_named_conf = custom_named_conf \
                .replace("//", "") \
                .replace("{ROUTER_NAME}", router_name) \
                .replace("{ORIGINAL_RESOLVER}", info["original_resolver"])
    with open(CUSTOM_NAMED_CONF, "w") as file:
        file.write(custom_named_conf)

    # COPY ORIGINAL BIND CONFIGURATION
    shutil.copy2(NAMED_CONF, NAMED_CONF + ".original")


def load() -> None:
    """Loads BIND configuration, generates files from it and restarts server."""
    # LOAD NAMED CONFIG
    conf = get_conf_dummy()

    with open(ZONE_TEMPLATE) as file:
        zone_template = file.read()
    # POLICIES & ZONES
    policies = " ".join(list(map(lambda x: 'zone "{0};"'.format(x), conf["block_zones"])))
    zones = "".join(
        list(map(lambda x: zone_template.replace("{ZONE}", x).replace("{FILE}", BIND_DIR + x), conf["block_zones"])))

    # WHITELIST DB.PASSTHRU
    if len(conf["whitelist_domains"]) > 0:
        with open(RPZ_HEADER_TEMPLATE) as file:
            passthru_zone = file.read()

        passthru_zone = passthru_zone \
            .replace("{ZONE}", "db.passthru") \
            .replace("{SERIAL}", datetime.datetime.now().strftime("%Y%m%d%H"))

        passthru_zone += "\n".join(list(map(lambda x: "{0}\tCNAME rpz_passthru.".format(x), conf["whitelist_domains"])))

        policies = 'zone "db.passthru"; ' + policies
        zones = passthru_zone + zones

    # FORWARDERS & DNS OVER TLS
    if conf["forward_over_tls"]:
        forwarders = "127.0.0.1 port 10853;"
        with open(SERVER_TEMPLATE) as file:
            server = file.read()

        with open(BLANK_DOT_CONF) as file:
            dot_conf = file.read()

        dot_conf = dot_conf.replace("{SERVER}", conf["forwarders"][0])

        with open(DOT_CONF, "w") as file:
            file.write(dot_conf)
    else:
        if "original_resolver" in conf["forwarders"]:
            forwarders = static_ip.get_info()["original_resolver"] + ";"
        else:
            forwarders = "; ".join(conf["forwarders"]) + ";"

        server = ""
        os.remove(DOT_CONF)

    # FILL ALL INFORMATION INTO NAMED CONFIGURATION
    with open(CUSTOM_NAMED_CONF) as file:
        custom_named_conf = file.read()

    custom_named_conf = custom_named_conf \
        .replace("{FORWARDERS}", forwarders) \
        .replace("{POLICIES}", policies) \
        .replace("{ZONES}", zones) \
        .replace("{SERVER}", server)

    with open(NAMED_CONF, "w") as file:
        file.write(custom_named_conf)

    # CHECK CONFIGURATION
    try:
        output = bash.call("sudo named-checkconf")
        if output != "":
            logging.critical("BIND9 config is corrupted:\n"
                             "{0}\n"
                             "Aborting now.".format(output))
            exit(-1)
    except bash.CallError as error:
        logging.critical("Error thrown while checking BIND9 config:\n"
                         "{0}\n"
                         "Aborting now.".format(error))

    # Reload BIND9
    logging.info("Reloading BIND9 and restarting stunnel for changes to take effect.")
    try:
        bash.call("sudo rndc reload")
        bash.call("sudo systemctl restart stunnel")
    except bash.CallError as error:
        logging.critical("Critical error restarting: {0}\nAborting now.".format(error))
        exit(-1)
    finally:
        logging.info("Reload successful.")


def retransfer() -> None:
    """Retransfer block zones from master server."""
    # TODO Check if needed?


def get_conf() -> dict:
    """"""
    return {}


def get_conf_dummy() -> dict:
    """Dummy function to get configuration as long as server connection is not possible."""
    return {
        "forwarders": ["9.9.9.9", "149.112.112.112"],
        "forward_over_tls": True,
        "block_zones": ["db.combination.31", "db.ip"],
        "whitelist_domains": ["awin1.com", "track.webgains.com"]
    }


def remove() -> None:
    """Stops the service and removes the installed components & created directories."""
    # TODO: program this lol^


def _sigterm_handler(signum, frame) -> None:
    """Handler set for SIGTERM if firewall is run as app, calls remove()."""
    logging.info("Signal SIGTERM sent. Calling remove() function.")
    remove()
    exit(0)


if __name__ == '__main__':
    main()
    # TODO: Add option to call remove instead of main of called with flag of some kind.
