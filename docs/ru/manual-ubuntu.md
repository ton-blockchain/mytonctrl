# Инструкция как стать валидатором используя mytonctrl (v0.2, OS Ubuntu)

### 1. Устанавливаем mytonctrl:
Скачиваем установочный скрипт от имени того пользователя, на чьё имя будет установлен mytonctrl. Настоятельно не советую устанавливать mytonctrl от имени root. В нашем случае от имени user:

```
wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh
```

![wget output](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

Запускаем установочный скрипт от имени администратора:

```
sudo bash install.sh -m full
```

Или, если нужна lite-версия:

```
sudo bash install.sh -m lite
```


Вот так выглядит успешная установка mytonctrl
(скрин)


### 2. Проверяем, что всё установилось правильно:
Запускаем mytonctrl от имени того пользователя, на чьё имя установили:

```
mytonctrl
```

Смотрим статус mytonctrl. Здесь нас интересует:

- Статус ядра mytoncore. Должен быть зелёным.
- Статус локального валидатора. Должен быть зелёным.
- Рассинхронизация локального валидатора. Вначале будет огромное число. После того, как валидатор свяжется с остальными валидаторами, число станет около 250к. Затем, по мере синхронизации валидатора, число будет уменьшаться. Как только число станет меньше 20 — значит, валидатор синхронизировался.

![status](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-status_ru.png)

Смотрим доступные кошельки. Кошелек validator_wallet_001 был создан при установке mytonctrl:

![wallet list](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)


### 3. Закидываем необходимое количество монет на кошелёк валидатора и активируем кошелёк:
Минимальное количество монет для участи в одних выборах можно посмотреть на сайте tonmon.xyz, раздел `Participants stakes`.

На скрине команда `vas` отображает историю переводов, а команда `aw` активирует кошелек:

![account history](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)


### 4. На данном этапе всё уже готово для работы валидатора
mytoncore будет автоматически участвовать в выборах — разделит баланс кошелька на две части и будет использовать их как ставку для участия в выборах. Можно самому в ручном режиме установить размер стейка:

`set stake 50000` — установили размер стейка в 50к монет. Если ставка была принята и мы стали валидатором, то забрать свою ставку мы сможем только на вторые выборы — таковы правила электора.

![setting stake](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

Не стесняйтесь команды help:

![help command](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-help_ru.png)

Логи mytoncrl можно смотреть в `~/.local/share/mytoncore/mytoncore.log` если он был установлен не от лица root, иначе в `/usr/local/bin/mytoncore/mytoncore.log`.

![logs](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)


### 5. Бонус.
Если вы запускаете валидатор в тестовой сети, то можно помайнить немного монет у PoW-гиверов. Для этого нужно установить несколько параметров. Майнинг начнется автоматически.

Устанавливаем адрес PoW-гивера (список можно взять отсюда https://test.ton.org/TestGrams-HOWTO.txt):

```
set powAddr "kf-kkdY_B7p-77TLn2hUhM6QidWrrsl8FYWCIvBMpZKprBtN"
```

Устанавливаем адрес своего кошелька, на который будет зачисляться вознаграждение:
```
set minerAddr "EQB1eouuAYyQogT7Sd4KzzBLBoSdLm77wVL10CrHjJON8w7E"
```
