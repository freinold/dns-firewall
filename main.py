#!/usr/bin/env python3
import subprocess


def bash(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=True, executable="/bin/bash")


def main() -> None:
    bash("sudo apt update")
    bash("sudo apt install bind9 bind9utils dnsutils -y")


if __name__ == '__main__':
    main()
