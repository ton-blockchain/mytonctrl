#!/bin/bash
set -e

mode="full"

# Get arguments
while getopts m: flag
do
	case "${flag}" in
    m) mode=${OPTARG};;
	esac
done

if [ "$mode" = "binaries" ]; then
  /usr/bin/func -APS /usr/share/ton/smartcont/stdlib.fc snominator-code.fc -W snominator-code.boc -o snominator-code.fif
  /usr/bin/fift snominator-code.fif
else
  /usr/bin/ton/crypto/func -APS /usr/src/ton/crypto/smartcont/stdlib.fc snominator-code.fc -W snominator-code.boc -o snominator-code.fif
  /usr/bin/ton/crypto/fift snominator-code.fif
fi
