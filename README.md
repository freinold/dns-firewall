# dns-firewall

This is an explanation for using the RPZ technology dns-firewall

## Run it

First you need to install the module "python-crontab" on your system:
```console
fw@dns-firewall:~ $ sudo python3 -m pip install python-crontab
```

Afterwards the script can be started by calling it using your python3 interpreter in the project root directory:
```console
fw@dns-firewall:~/dns-firewall $ sudo python3 main.py <option>
```
Therefore you can specify 4 different options:
* `start`       - runs the firewall; if not installed, generates needed configurations and installs dependencies first
* `stop`        - terminates the running firewall
* `reconfigure` - reruns the whole configuration process for an already installed firewall
* `remove`      - terminates the running firewall and removes all installed dependencies and created files

## Configure it

The configuration files can be found in the directory `/etc/dns-fw/`. 

### Firewall configuration

To configure your firewall, change the contents of `/etc/dns-fw/fw.conf.json`.
* `forwarders` - enter either IP-addresses of the resolvers you want to use or the name(s) of the known resolvers in `~/dns-firewall/resources/forwarders.json`
* `forward_over_tls` - choose `true` if you want to use DNS over TLS (DoT) encryption to communicate with the resolver, `false` otherwise; **Warning:** The chosen resolver has to support DoT in order for this to function properly, otherwise the firewall will have no connection to the DNS at all!
* `block_zones` - pick the domain categories you want to block, currently supported are "suspicious", "advertising", "tracking", "malicious", "bitcoin" and the special IP-address category "ip"
* `whitelist_domains` - enter domains which you want to pass through the firewall no matter if they may be in one of the block zones

To reload the new configuration run:
```console
fw@dns-firewall:~/dns-firewall $ sudo python3 main.py start
```

### Static ip-address configuration

To change the automatic configuration of a static ip-address, use the file `/etc/dns-fw/static_ip.info.json`
Values used for the configuration are `interface`, `static_ip`, `router` and `resolver`. 
**Do not change the other values!**

To reconfigure the static ip with the changed settings run:
```console
fw@dns-firewall:~/dns-firewall $ sudo python3 main.py reconfigre
```