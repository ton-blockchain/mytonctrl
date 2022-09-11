#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

post="/bin/echo service down"
user=root
group=root

while getopts n:s:p:u:g: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    s) start=${OPTARG};;
    p) post=${OPTARG};;
    u) user=${OPTARG};;
    g) group=${OPTARG};;
	esac
done

if [ -z "$name" ]; then
  echo "name is empty"
  exit 1
fi

if [ -z "$start" ]; then
  echo "start is empty"
  exit 1
fi


DAEMON_PATH="/etc/systemd/system/${name}.service"

cat <<EOF > $DAEMON_PATH
[Unit]
Description = $name service. Created by https://github.com/igroman787/mypylib.
After = network.target

[Service]
Type = simple
Restart = always
RestartSec = 30
ExecStart = $start
ExecStopPost = $post
User = $user
Group = $group
LimitNOFILE = infinity
LimitNPROC = infinity
LimitMEMLOCK = infinity

[Install]
WantedBy = multi-user.target
EOF

chmod 664 $DAEMON_PATH
chmod +x $DAEMON_PATH
systemctl daemon-reload
systemctl enable ${name}
