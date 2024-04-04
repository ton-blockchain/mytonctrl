#!/bin/bash

check_superuser() {
	if [ "$(id -u)" != "0" ]; then
		echo "Please run script as root"
		exit 1
	fi
}

get_cpu_number() {
	if [[ "$OSTYPE" =~ darwin.* ]]; then
		cpu_number=$(sysctl -n hw.logicalcpu)
	else
		memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
		cpu_number=$(($memory/2100000))
		max_cpu_number=$(nproc)
		if [ ${cpu_number} -gt ${max_cpu_number} ]; then
			cpu_number=$((${max_cpu_number}-1))
		fi
		if [ ${cpu_number} == 0 ]; then
			echo "Warning! insufficient RAM"
			cpu_number=1
		fi
	fi
	echo ${cpu_number}
}

check_go_version() {
	go_mod_path=${1}
	go_path=${2}
	go_mod_text=$(cat ${go_mod_path}) || exit 1
	need_version_text=$(echo "${go_mod_text}" | grep "go " | head -n 1 | awk '{print $2}')
	current_version_text=$(${go_path} version | awk '{print $3}' | sed 's\go\\g')
	echo "start check_go_version function, need_version: ${need_version_text}, current_version: ${current_version_text}"
	current_version_1=$(echo ${current_version_text} | cut -d "." -f 1)
	current_version_2=$(echo ${current_version_text} | cut -d "." -f 2)
	current_version_3=$(echo ${current_version_text} | cut -d "." -f 3)
	need_version_1=$(echo ${need_version_text} | cut -d "." -f 1)
	need_version_2=$(echo ${need_version_text} | cut -d "." -f 2)
	need_version_3=$(echo ${need_version_text} | cut -d "." -f 3)
	if (( need_version_1 > current_version_1 )) || ((need_version_2 > current_version_2 )) || ((need_version_3 > current_version_3 )); then
		install_go
	fi
}

install_go() {
	echo "start install_go function"
	arc=$(dpkg --print-architecture)
	go_version_url=https://go.dev/VERSION?m=text
	go_version=$(curl -s ${go_version_url} | head -n 1)
	go_url=https://go.dev/dl/${go_version}.linux-${arc}.tar.gz
	rm -rf /usr/local/go
	wget -c ${go_url} -O - | tar -C /usr/local -xz
}
