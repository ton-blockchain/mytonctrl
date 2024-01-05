#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

file_path=/var/ton-work/db/test.img
db_path=/var/ton-work/db/bench

function get_fio_json {
	read_iops=$(echo "$1" | grep "read:" | awk '{print $2}' | awk -F '=' '{print $2}')
	write_iops=$(echo "$1" | grep "write:" | awk '{print $2}' | awk -F '=' '{print $2}')
	read_iops=$(echo "${read_iops//,/}")
	write_iops=$(echo "${write_iops//,/}")
	read_speed=$(echo "$1" | grep "read:" | awk '{print $3}' | awk -F '=' '{print $2}')
	write_speed=$(echo "$1" | grep "write:" | awk '{print $3}' | awk -F '=' '{print $2}')
	json=$(cat <<-END
	{
		"read_iops": "${read_iops}",
		"write_iops": "${write_iops}",
		"read_speed": "${read_speed}",
		"write_speed": "${write_speed}"
	}
	END
	)
	echo $json
}

function get_rocksd_bench_json {
	random_ops=$(echo "$1" | grep "randomtransaction" | awk '{print $5}')
	json=$(cat <<-END
	{
		"random_ops": "${random_ops}"
	}
	END
	)
	echo $json
}

function print_json_result {
	json=$(cat <<-END
	{
		"lite": ${lite_json_result},
		"hard": ${hard_json_result},
		"full": ${full_json_result}
	}
	END
	)
	echo $json
}

# https://superuser.com/questions/1049382/ssd-4k-random-read-write-qd1-32-and-iops-values
# lite
lite_result=$(fio --name=test --runtime=60 --readwrite=randrw --blocksize=4k --ioengine=libaio --direct=1 --size=4G --filename=${file_path} --rwmixread=75 --randrepeat=1 --gtod_reduce=1 --iodepth=64)
lite_json_result=$(get_fio_json "$lite_result")

# hard
hard_result=$(fio --name=test --runtime=60 --readwrite=randrw --blocksize=4k --ioengine=libaio --direct=1 --size=4G --filename=${file_path} --rwmixread=75 --io_size=10g --fsync=1 --iodepth=1 --numjobs=1)
hard_json_result=$(get_fio_json "$hard_result")

# full
full_result=$(/usr/bin/db_bench --benchmarks="randomtransaction" -max_background_flushes 2 max_background_compactions 4 -bytes_per_sync 1048576 -writable_file_max_buffer_size 32768 -duration 60 -threads 8 -db=${db_path} 2>/dev/null)
full_json_result=$(get_rocksd_bench_json "$full_result")

# clear temp files
rm ${file_path}
rm -rf ${db_path}

print_json_result
