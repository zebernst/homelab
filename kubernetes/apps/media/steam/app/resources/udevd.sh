#!/usr/bin/env sh

echo "\e[36m  - Ensure 'systemd-udevd' is running...\e[0m"
sudo /lib/systemd/systemd-udevd --daemon >/dev/null 2>&1
