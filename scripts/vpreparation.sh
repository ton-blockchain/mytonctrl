#!/bin/sh

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Запустите скрипт от имени администратора"
	exit 1
fi

# Цвета
COLOR='\033[93m'
ENDC='\033[0m'

# Генерация порта для валидатора
ip=127.0.0.1 ### fix me
echo -e "${COLOR}[1/6]${ENDC} Генерируем для валидатора порт подключения"
port=$(shuf -i 2000-65000 -n 1)
addr=${ip}:${port}
echo "${port}" > /tmp/vport.txt

# Создать переменные
dbPath=/var/ton-work/db
logPath=/var/ton-work/log
validatorAppPath=/usr/bin/ton/validator-engine/validator-engine
validatorConfig=/usr/bin/ton/validator-engine/ton-global.config.json

# Подготовить папки валидатора
echo -e "${COLOR}[2/6]${ENDC} Подготавливаем папку валидатора"
rm -rf ${dbPath}
mkdir -p ${dbPath}

# Создать пользователя
echo -e "${COLOR}[3/6]${ENDC} Создаем нового пользователя 'validator' для работы валидатора"
useradd -d /dev/null -s /dev/null validator

# Проверка первого запуска валидатора
configPath=${dbPath}/config.json
rm -f ${configPath}

# Первый запуск валидатора
echo -e "${COLOR}[4/6]${ENDC} Создаем конфигурационный файл валидатора"
${validatorAppPath} -C ${validatorConfig} --db ${dbPath} --ip ${addr} -l ${logPath}

# Сменить права на нужные директории
chown -R validator:validator /var/ton-work

# Создать копию конфигурации во времянной папке
cp -r ${configPath} /tmp/vconfig.json
chmod 777 /tmp/vconfig.json

# Прописать автозагрузку в cron
echo -e "${COLOR}[5/6]${ENDC} Прописываем автозагрузку валидатора через cron от имени пользователя 'validator'"
cmd="${validatorAppPath} -d -C ${validatorConfig} --db ${dbPath} --ip ${addr} -l ${logPath}"
cronText="@reboot /bin/sleep 60 && ${cmd}"
echo "${cronText}" > mycron && crontab -u validator mycron && rm mycron

# Конец
echo -e "${COLOR}[6/6]${ENDC} Настройка валидатора завершина"
