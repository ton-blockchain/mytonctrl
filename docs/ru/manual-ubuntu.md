# Как стать валидатором с помощью mytonctrl (v0.2, ОС Ubuntu)

Вот шаги по становлению валидатором с использованием mytonctrl. Этот пример применим для операционной системы Ubuntu.

## 1. Установка mytonctrl:

1. Загрузите скрипт установки. Мы рекомендуем устанавливать инструмент под вашей локальной учетной записью пользователя, а не как Root. В нашем примере используется локальная учетная запись пользователя:

    ```sh
    wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
    ```

    ![wget output](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

2. Запустите скрипт установки как администратор:

    ```sh
    sudo bash install.sh -m full
    ```

## 2. Тест на работоспособность:

1. Запустите **mytonctrl** с локальной учетной записью пользователя, используемой для установки на шаге 1:

    ```sh
    mytonctrl
    ```

2. Проверьте статусы **mytonctrl**, в частности следующие:

* **mytoncore status**: должен быть зеленым.
* **Local validator status**: также должен быть зеленым.
* **Local validator out of sync**: Сначала отображается большое число. Как только новый валидатор подключается к другим валидаторам, число будет около 250k. По мере синхронизации это число уменьшается. Когда оно падает ниже 20, валидатор синхронизирован.

    ![status](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)

Смотрим доступные кошельки. Кошелек validator_wallet_001 был создан при установке mytonctrl:

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)

## 3. Просмотр списка доступных кошельков
Просмотрите список доступных кошельков. В нашем примере кошелек **validator_wallet_001** был создан при установке **mytonctrl**:

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)

## 4. Отправьте необходимое количество монет в кошелек и активируйте его
Чтобы проверить минимальное количество монет, необходимое для участия в одном раунде выборов, перейдите на **tonmon.xyz** > **Участники ставок**.

* Команда `vas` отображает историю переводов
* Команда `aw` активирует кошелек

    ![account history](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)

## 5. Теперь ваш валидатор готов к работе
**mytoncore** автоматически присоединяется к выборам. Он делит баланс кошелька на две части и использует их в качестве ставки для участия в выборах. Вы также можете вручную установить размер ставки:

`set stake 50000` — установить размер ставки в 50k монет. Если ставка принята и наш узел становится валидатором, ставку можно вернуть только на вторых выборах (согласно правилам электората).

![setting stake](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

Не стесняйтесь обращаться за помощью.

![help command](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-help_ru.png)

Для проверки логов **mytoncrl** откройте `~/.local/share/mytoncore/mytoncore.log` для локального пользователя или `/usr/local/bin/mytoncore/mytoncore.log` для Root.

![logs](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)