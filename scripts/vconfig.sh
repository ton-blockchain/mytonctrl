#!/bin/sh

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Запустите скрипт от имени администратора"
	exit 1
fi

# Проверка режима
if [ "${1}" != "-kh" ]; then
	echo "Запустите скрипт в режиме импорта ключа: '-kh <server_key_hex>'"
	exit 1
fi

# Цвета
COLOR='\033[94m'
ENDC='\033[0m'

# Создать переменные
ip=127.0.0.1 ### fix me
dbPath=/var/ton-work/db &&
logPath=/var/ton-work/log &&
validatorAppPath=/usr/bin/ton/validator-engine/validator-engine &&
validatorConfig=/usr/bin/ton/validator-engine/ton-global.config.json &&
port=$(cat /tmp/vport.txt) &&
addr=${ip}:${port} &&

# Перемещаем наши ключи в нужную папку
echo -e "${COLOR}[1/4]${ENDC} Перемещаем наши ключи в нужную папку"
server_key_hex=${2} &&
mv /tmp/vkeys/server ${dbPath}/keyring/${server_key_hex} &&
mv /tmp/vkeys/server.pub /usr/bin/ton/validator-engine-console/server.pub &&
mv /tmp/vkeys/client /usr/bin/ton/validator-engine-console/client &&
mv /tmp/vkeys/client.pub /usr/bin/ton/validator-engine-console/client.pub &&


# Прописать наши ключи в конфигурационном файле валидатора
echo -e "${COLOR}[2/4]${ENDC} Прописываем наши ключи в конфигурационном файле валидатора"
cat /tmp/vconfig.json > ${dbPath}/config.json &&

# Запустить валидатор
echo -e "${COLOR}[3/4]${ENDC} Запускаем валидатор от имени пользователя 'validator'"
cmd="${validatorAppPath} -d -C ${validatorConfig} --db ${dbPath} --ip ${addr} -l ${logPath}" &&
su -l validator -s /bin/sh -c "${cmd} &" &&

# Поправить права на папку
chown -R validator:validator /var/ton-work &&

# Конец
echo -e "${COLOR}[4/4]${ENDC} Перенастройка валидатора завершена"


