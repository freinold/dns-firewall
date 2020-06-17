#!/usr/bin/env python3
import argparse
import datetime
import json
import logging
import os
import shutil
import signal

import time

import bash
import static_ip

# import pi_baseclient.bash as bash
# import pi_baseclient.static_ip as static_ip


FW_DIR = "/etc/dns-fw/"
FW_LOG = "/etc/dns-fw/log"
FW_CONF = "/etc/dns-fw/fw.conf.json"
FW_IS_INSTALLED = "/etc/dns-fw/installed"
CUSTOM_NAMED_CONF = "/etc/dns-fw/named.conf"

BIND_DIR = "/etc/bind/"
NAMED_CONF = "/etc/bind/named.conf"
NAMED_CONF_LOGGING = "/etc/bind/named.conf.logging"
DB_PASSTHRU = "/etc/bind/db.passthru"

DOT_CONF = "/etc/stunnel/dot.conf"

NAMED_CACHE_DIR = "/var/cache/named/"
NAMED_LOG_DIR = "/var/log/named/"

BASIC_FW_CONF = "resources/basic_fw.conf.json"
BLANK_DOT_CONF = "resources/dot.conf"
BLANK_NAMED_CONF = "resources/named.conf"
PRECONFIGURED_NAMED_CONF_LOGGING = "resources/named.conf.logging"
NAMED_LOGFILES = "resources/named_logfiles"
SLAVE_ZONE_TEMPLATE = "resources/slave_zone_template"
FORWARD_ZONE_TEMPLATE = "resources/forward_zone_template"
MASTER_ZONE_TEMPLATE = "resources/master_zone_template"
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


class Configuration:
    def __init__(self, filename=None):
        self.forwarders: list
        self.forward_over_tls: bool
        self.block_zones: list
        self.whitelist_domains: list
        if filename is not None:
            with open(filename) as file:
                configuration = json.load(file)
            self.forwarders = configuration["forwarders"]
            self.forward_over_tls = configuration["forward_over_tls"]
            self.block_zones = configuration["block_zones"]
            self.whitelist_domains = configuration["whitelist_domains"]


def main() -> None:
    """Entry point used if script is called directly."""
    parser = argparse.ArgumentParser(prog="dns-firewall", description="DNS-Firewall for filtering DNS-Queries")
    parser.add_argument("action", default="start",
                        help="One of 'start', 'stop', 'reconfigure' or 'remove'; default is 'start'")
    args = parser.parse_args()
    print(LOGO)
    make_directories()
    configure_logs(interactive=True)
    if args.action == "start":
        if not os.path.isfile(FW_IS_INSTALLED):
            logging.warning("Software is not installed.")
            configure(install_packages=True)
        load()
    elif args.action == "reconfigure":
        os.remove(FW_IS_INSTALLED)
        configure(install_packages=False)
        load()
    elif args.action == "stop":
        stop()
    elif args.action == "remove":
        stop()
        remove(remove_packages=True, interactive=True)


def run() -> None:
    """Entry point used if called by app controller."""
    signal.signal(signal.SIGTERM, _sigterm_handler)
    make_directories()
    configure_logs(interactive=False)
    if not os.path.isfile(FW_IS_INSTALLED):
        configure()
    load()


def make_directories() -> None:
    """Creates needed directories in /etc and /var."""
    for directory in [FW_DIR, NAMED_LOG_DIR, NAMED_CACHE_DIR]:
        if not os.path.isdir(directory):
            os.makedirs(directory)

    shutil.chown(NAMED_LOG_DIR, user="bind", group="bind")
    shutil.chown(NAMED_CACHE_DIR, user="bind", group="bind")


def configure_logs(interactive: bool = False) -> None:
    """Configures logging, either interactive or to file."""
    if interactive:
        # noinspection PyArgumentList
        logging.basicConfig(
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            format="{asctime} - {levelname:8}: {message}",
            level=logging.DEBUG,
            style="{"
        )
    else:
        if not os.path.isfile(FW_LOG):
            os.mknod(FW_LOG)
        # noinspection PyArgumentList
        logging.basicConfig(
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            filename=FW_LOG,
            filemode="a",
            format="{asctime} - {levelname:8}: {message}",
            level=logging.INFO,
            style="{"
        )
    logging.info("DNS-FIREWALL started.")


def configure(install_packages=False) -> None:
    """Installs the dependencies, sets static ip and builds general custom BIND9 configuration."""
    logging.warning("Starting configuration now.")
    # DOWNLOAD PACKAGES (IF NOT DONE BY APP-CONTROLLER)
    if install_packages:
        logging.info("Downloading all required packages.")
        with open("metadata.json") as file:
            apt_packages = json.load(file)["apt"]
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
    logging.info("Checking if static IP is already configured.")
    if not static_ip.is_configured():
        logging.info("Static IP was not configured, starting configuration now.")
        static_ip.configure()
        logging.info("Static IP configuration successful, waiting 10 seconds for changes to come into effect.")
        time.sleep(10)
    elif not static_ip.is_info():
        logging.info("Required context information of static IP configuration not found, reconfiguration needed.")
        static_ip.revert()
        logging.info("Reverted IP settings, sleeping 10 seconds for changes to come into effect.")
        time.sleep(10)
        static_ip.configure(self_as_resolver=False)
        logging.info("Configured new IP settings, sleeping 10 seconds for changes to come into effect.")
        time.sleep(10)

    info = static_ip.Info(filename=static_ip.INFO_FILE)
    logging.info("Static IP configuration finished.")

    # QUERY OLD RESOLVER FOR PTR RECORDS OF ROUTER
    try:
        router_names = bash.call("dig @{0} -x {1} | "
                                 "grep PTR | "
                                 "awk '{{print $5}}'".format(info.original_resolver.compressed,
                                                             info.router.compressed)).splitlines()
        logging.debug("Router names non formatted: {0}".format(router_names))
        router_names = list(map(lambda x: x[:-1], filter(lambda x: len(x) > 0, router_names)))
        logging.debug("Router names formatted: {0}".format(router_names))

    except bash.CallError:
        logging.error("Error: Could not retrieve routers name from original resolver. Access via domain not possible.")
        router_names = []

    # BUILD CUSTOM BIND CONFIGURATION
    with open(BLANK_NAMED_CONF) as file:
        custom_named_conf = file.read()

    custom_named_conf = custom_named_conf.replace("{SUBNET}", info.subnet.compressed)

    forward_zones = ""

    if len(router_names) > 0:
        with open(FORWARD_ZONE_TEMPLATE) as file:
            forward_zone_template = file.read()

        for name in router_names:
            forward_zones += forward_zone_template.replace("{NAME}", name) \
                .replace("{FORWARDER}", info.original_resolver.compressed)

    custom_named_conf = custom_named_conf.replace("{FORWARD_ZONES}", forward_zones)

    with open(CUSTOM_NAMED_CONF, "w") as file:
        file.write(custom_named_conf)

    # SET UP BIND LOGS
    shutil.copy2(PRECONFIGURED_NAMED_CONF_LOGGING, NAMED_CONF_LOGGING)

    with open(NAMED_LOGFILES) as file:
        named_logfiles = file.readlines()

    for logfile in named_logfiles:
        logfile_path = os.path.join(NAMED_LOG_DIR, logfile.strip())
        if not os.path.isfile(logfile_path):
            os.mknod(logfile_path, mode=0o644)
        shutil.chown(logfile_path, user="bind", group="bind")

    # COPY ORIGINAL BIND CONFIGURATION
    shutil.copy2(NAMED_CONF, NAMED_CONF + ".original")

    # COPY BASIC CONFIG TO FW DIR
    shutil.copy2(BASIC_FW_CONF, FW_CONF)

    os.mknod(FW_IS_INSTALLED)


def load() -> None:
    """Loads BIND configuration, generates files from it and restarts server."""
    logging.info("Starting load of individual configuration.")
    # LOAD NAMED CONFIG
    configuration = Configuration(filename=FW_CONF)

    # POLICIES & SLAVE ZONES
    logging.info("Generating slave blocking zones.")
    with open(SLAVE_ZONE_TEMPLATE) as file:
        zone_template = file.read()
    policies = " ".join(list(map(lambda x: 'zone "{0}";'.format(x), configuration.block_zones)))
    slave_zones = "".join(
        list(map(lambda x: zone_template.replace("{NAME}", x).replace("{FILE}", NAMED_CACHE_DIR + x),
                 configuration.block_zones)))

    # WHITELIST DB.PASSTHRU
    logging.info("Generating whitelist zone.")
    if len(configuration.whitelist_domains) > 0:
        with open(RPZ_HEADER_TEMPLATE) as file:
            db_passthru = file.read()

        db_passthru = db_passthru \
            .replace("{ZONE}", "db.passthru") \
            .replace("{SERIAL}", datetime.datetime.now().strftime("%Y%m%d%H"))

        db_passthru += "\n".join(
            list(map(lambda x: "{0}\tCNAME rpz-passthru.".format(x), configuration.whitelist_domains))) + "\n"

        with open(DB_PASSTHRU, "w") as file:
            file.write(db_passthru)

        policies = 'zone "db.passthru"; ' + policies

        with open(MASTER_ZONE_TEMPLATE) as file:
            passthru_zone = file.read()

        passthru_zone = passthru_zone.replace("{NAME}", "db.passthru").replace("{FILE}", DB_PASSTHRU)
    else:
        os.remove(DB_PASSTHRU)
        passthru_zone = ""

    # FORWARDERS & DNS OVER TLS
    logging.info("Generating forwarding configuration.")
    if configuration.forward_over_tls:
        forwarders = "127.0.0.1 port 10853;"
        with open(SERVER_TEMPLATE) as file:
            server = file.read()

        with open(BLANK_DOT_CONF) as file:
            dot_conf = file.read()

        dot_conf = dot_conf.replace("{SERVER}", configuration.forwarders[0])

        with open(DOT_CONF, "w") as file:
            file.write(dot_conf)
    else:
        if "original_resolver" in configuration.forwarders:
            forwarders = static_ip.Info(static_ip.INFO_FILE).original_resolver + ";"
        else:
            forwarders = "; ".join(configuration.forwarders) + ";"

        os.remove(DOT_CONF)
        server = ""

    # FILL ALL INFORMATION INTO NAMED CONFIGURATION
    logging.info("Fill BIND9 configuration with generated statements.")
    with open(CUSTOM_NAMED_CONF) as file:
        custom_named_conf = file.read()

    custom_named_conf = custom_named_conf \
        .replace("{FORWARDERS}", forwarders) \
        .replace("{POLICIES}", policies) \
        .replace("{PASSTHRU_ZONE}", passthru_zone) \
        .replace("{SLAVE_ZONES}", slave_zones) \
        .replace("{SERVER}", server)

    with open(NAMED_CONF, "w") as file:
        file.write(custom_named_conf)

    # CHECK CONFIGURATION
    logging.info("Checking BIND9 configuration.")
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
    logging.info("Reloading BIND9 / stunnel for changes to take effect.")
    try:
        if configuration.forward_over_tls:
            bash.call("sudo systemctl restart stunnel4")
        else:
            bash.call("sudo systemctl stop stunnel4")
        bash.call("sudo rndc reload")
    except bash.CallError as error:
        logging.critical("Critical error restarting: {0}\nAborting now.".format(error))
        exit(-1)
    finally:
        logging.info("Reload successful.")


def stop() -> None:
    """Stops the running services"""
    logging.info("Stopping BIND and stunnel.")
    bash.call("sudo systemctl stop bind9")
    bash.call("sudo systemctl stop stunnel4")
    logging.info("Both services stopped successfully.")


def remove(remove_packages=False, interactive=False) -> None:
    """Removes the installed components & created directories."""
    if interactive:
        confirmation = input("Are you sure you want to delete dns-firewall? [ Yes ]")
        if confirmation != "Yes":
            exit(0)
    logging.info("Removing application directory {0}.".format(FW_DIR))
    bash.call("rm -rf {0}".format(FW_DIR))
    logging.info("Application directory removed.")
    if remove_packages:
        logging.info("Removing all packages.")
        with open("metadata.json") as file:
            apt_packages = json.load(file)["apt"]
        try:
            bash.call("sudo apt remove {0} -y".format(" ".join(apt_packages)))
            bash.call("sudo apt autoremove")
        except bash.CallError as error:
            logging.critical("Critical error removing packages:\n"
                             "{0}\n"
                             "Aborting now.".format(error))
            exit(-1)
        finally:
            logging.info("Packages removed successfully.")


def _sigterm_handler(signum, frame) -> None:
    """Handler set for SIGTERM if firewall is run as app, calls stop & remove, but doesn't remove packages."""
    logging.info("Signal SIGTERM sent. Stopping and removing application.")
    stop()
    remove()
    exit(0)


if __name__ == '__main__':
    main()
