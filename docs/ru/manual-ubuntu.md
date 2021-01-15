# Инструкция как стать валидатором используя mytonctrl (v0.2, OS Ubuntu)
#### 1. Устанавливаем mytonctrl:
Скачиваем установочный скрипт от имени того пользователя, на чье имя будет установлен mytonctrl. Настоятельно не советую устанавливать mytonctrl от имени root. В нашем случае от имени user:
`wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh`
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

Запускаем установочный скрипт от имени администратора:
`sudo bash install.sh -m full`

Вот так выглядит успешная установка mytonctrl
(скрин)

#### 2. Проверка что все установилось правильно:
Запускаем mytonctrl от имени того пользователя, на чье имя установили:
`mytonctrl`

Смотрим статус mytonctrl. Здесь нас интересует:
- Статус ядра mytoncore. Должен быть зеленым.
- Статус локального валидатора. Должен быть зеленым.
- Рассинхронизация локального валидатора. Вначале будет огромное число. После того, как валидатор свяжется с остальными валидаторами, число станет около 250к. Затем по мере синхронизации валидатора число будет уменьшаться. Как только число станет меньше 20 - значит валидатор синхронизировался.
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-status_ru.png)

Смотрим доступные кошельки. Кошелек validator_wallet_001 был создан при установке mytonctrl:
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)

#### 3. Закидываем необходимое количество монет на кошелек валидатора и активируем кошелек. Минимальное количество монет для участи в одних выборах можно посмотреть на сайте tonmon.xyz, раздел `Participants stakes`. На скрине команда `vas` отображает историю переводов, а команда `aw` активирует кошелек:
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)

#### 4. На данном этапе все уже готово для работы валидатора. mytoncore автоматически будет участвовать в выборах. разделит баланс кошелька на две части и будет их использовать как ставку для участия в выборах. Можно самому в ручном режиме установить размер стейка:
`set stake 50000` - установили размер стейка в 50к монет. Если ставка была принята и мы стали валидатором, то забрать свою ставку мы сможем только на вторые выборы - таковы правила электора.
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

Не стесняйтесь команды help:
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytonctrl-help_ru.png)

Логи mytoncre можно смотреть тут:
`~/.local/share/mytoncore/mytoncore.log`
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)

#### 5. Бонус.
Если вы запускаете валидатор в тестовой сети, то можно помайнить немного монет у PoW гиверов. Для этого нужно установить несколько параметров. Майнинг начнется автоматически:
`set powAddr "kf-kkdY_B7p-77TLn2hUhM6QidWrrsl8FYWCIvBMpZKprBtN"` - установить адрес PoW гивера, список можно взять отсюда https://test.ton.org/TestGrams-HOWTO.txt
`set minerAddr "EQB1eouuAYyQogT7Sd4KzzBLBoSdLm77wVL10CrHjJON8w7E"` - установить адрес своего кошелька, на который будет зачисляться вознаграждение.
