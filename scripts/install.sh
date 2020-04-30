#!/bin/sh

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Запустите скрипт от имени администратора"
	exit 1
fi

# Проверка режима установки
if [ "${1}" != "-m" ]; then
	echo "Запустите скрипт в одном из двух режимов: '-m lite' или '-m full'"
	exit 1
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Почистить папки
rm -rf /tmp/vkeys/
rm -rf /tmp/mytonsettings.json
rm -rf /tmp/vport.txt
rm -rf /tmp/vconfig.json

# Начинаю установку mytonctrl
echo -e "${COLOR}[1/4]${ENDC} Начинаю установку mytonctrl"
mode=${2}

# Проверяю наличие компонентов TON
echo -e "${COLOR}[2/4]${ENDC} Проверяю наличие компонентов TON"
file1=/usr/bin/ton/crypto/fift
file2=/usr/bin/ton/lite-client/lite-client
file3=/usr/bin/ton/validator-engine-console/validator-engine-console
if [ -f "${file1}" ] && [ -f "${file2}" ] && [ -f "${file3}" ]; then
	echo "TON exist"
else
	rm -f toninstaller.sh
	wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/toninstaller.sh
	sh toninstaller.sh
	rm -f toninstaller.sh
fi

# Запускаю установщик mytoninstaller.py
echo -e "${COLOR}[3/4]${ENDC} Запускаю установщик mytoninstaller.py"
user=$(ls -lh install.sh | cut -d ' ' -f 3)
su -l ${user} -c "python3 /usr/src/mytonctrl/mytoninstaller.py -m ${mode}"

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} Установка mytonctrl завершина"
exit 0
