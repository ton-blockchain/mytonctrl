#!/bin/bash
set -e

stats=$(validator-console -c getstats)
unixtime=$(echo "$stats" | grep unixtime | awk '{print $2}')
mastertime=$(echo "$stats" | grep masterchainblocktime | awk '{print $2}')
if [ -z $mastertime ]
then
	result="mastertime is None"
else
	result=$(($unixtime-$mastertime))
fi

echo $result
