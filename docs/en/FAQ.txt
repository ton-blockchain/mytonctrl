Used directories:
mytonctrl is a wrapper and stores its files in two places:
1. ~/.local/share/mytonctrl/ - persistent files such as logs
2. /tmp/mytonctrl/ - temporary files

mytonctrl also contains another script mytoncore, which in turn stores files here:
1. ~/.local/share/mytoncore/ - permanent files, the main config will be stored here
2. /tmp/mytoncore/ - temporary files, there will be saved parameters used for elections

mytonctrl downloads the source code of itself and the validator into folders:
1. /usr/src/mytonctrl/
2. /usr/src/ton/

mytonctrl compiles the components of the validator into a folder:
1. /usr/bin/ton/

mytonctrl creates a folder for the validator to work here:
1. /var/ton/

===========================================================================================================

If mytonctrl was installed as root:
Then the configurations will lie in a different way:
1. /usr/local/bin/mytonctrl/
2. /usr/local/bin/mytoncore/

===========================================================================================================

How to remove mytonctrl:
run the script as administrator and remove the compiled TON components:
`sudo bash /usr/src/mytonctrl/scripts/uninstall.sh`
`sudo rm -rf /usr/bin/ton`

===========================================================================================================

If we run mytonctrl as a different user, we get the following error. The solution is to run as the user from whom you installed:
`Error: expected str, bytes or os.PathLike object, not NoneType`
(error screen + normal startup screen)

===========================================================================================================

If we want to change the working directory of the validator before installation, then there are two options:
1.fork the project and make our changes (man git-fork)
2.or create a symbolic link:
`ln -s /opt/ton/var/ton` - Create a link /var/ton that leads to /opt/ton

===========================================================================================================

If we want to change the working directory of the validator from /var/ton/, then after installation we will do the following:
1.` systemctl stop validator`, `systemctl stop mytoncore` - Stop services
2.`mv /var/ton/* /opt/ton/`- move the validator files
3. Replace the paths in the configuration `~ /.local/share/mytoncore/mytoncore.db`
4. Then we look at the circumstance - there was no experience of such a transfer