pip3 uninstall -y mytonctrl

cd /usr/src
rm -rf mytonctrl
git clone --recursive -b mytonctrl1 https://github.com/ton-blockchain/mytonctrl

echo "Updating /usr/bin/mytonctrl"
echo "/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py $@" > /usr/bin/mytonctrl
chmod +x /usr/bin/mytonctrl

echo "Updating mytoncore service"
sed -i 's\-m mytoncore\/usr/src/mytonctrl/mytoncore.py\g' /etc/systemd/system/mytoncore.service
systemctl daemon-reload
systemctl restart mytoncore

echo "Done"
