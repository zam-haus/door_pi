# Raspi Setup

## Hardware

* Raspberry PI 4B (2 GB)
* PoE+ Hat for RasPi 4 Model B (25 W)
* door_if Hat

## Raspi Configuration

### PoE Fan Control

*/boot/config.txt (section [all]):*

	dtparam=poe_fan_temp0=60000
	dtparam=poe_fan_temp1=65000
	dtparam=poe_fan_temp2=70000
	dtparam=poe_fan_temp3=75000

### Disable WLAN and Bluetooth

*/boot/config.txt (general section):*
	dtoverlay=disable-wifi
	dtoverlay=disable-bt

### Read-Only Filesystem

*according to* [c't 26/2021](https://www.heise.de/select/ct/2021/16/2112313321295857638) 

* install network-manager:

		apt-get install network-manager
		systemctl enable --now NetworkManager
		cd /etc
		ln -sf ../run/NetworkManager/resolv.conf
		
* configure kernel boot in /boot/cmdline.txt
    * ... root=... **ro** rootfstype=ext4 ...
* configure filesystems in /etc/fstab
    * ... /boot vfat **ro,**defaults ...
    * ... / ext4 **ro,**defaults,noatime ...
* add tmpfs in /etc/fstab:

		tmpfs           /var/lib/systemd   tmpfs     mode=0755               0 0
		tmpfs           /var/lib/private   tmpfs     mode=0700               0 0
		tmpfs           /var/log           tmpfs     nodev,nosuid            0 0
		tmpfs           /var/tmp           tmpfs     nodev,nosuid            0 0
		tmpfs           /var/cache         tmpfs     nodev,nosuid            0 0
		tmpfs           /tmp               tmpfs     nodev,nosuid,mode=1777  0 0

* disable swap

		systemctl disable dphys-swapfile

* shell highlighting /root/.bashrc

		export LS_OPTIONS='--color=auto'
		eval "`dircolors`"
		alias ls='ls $LS_OPTIONS'
		alias ll='ls $LS_OPTIONS -la'
		alias l='ls $LS_OPTIONS'
		set_bash_prompt() {
			fs_mode=$(mount | sed -n -e "s/^\/dev\/.* on \/ .*(\(r[w|o]\).*/\1/p")
			PS1='\[\033[01;31m\]\u@\h${fs_mode:+($fs_mode)}\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
		}
		alias ro='sudo mount -o remount,ro / ; sudo mount -o remount,ro /boot'
		alias rw='sudo mount -o remount,rw / ; sudo mount -o remount,rw /boot'
		PROMPT_COMMAND=set_bash_prompt

* shell highlighting /home/pi/.bashrc

		export LS_OPTIONS='--color=auto'
		eval "`dircolors`"
		alias ls='ls $LS_OPTIONS'
		alias ll='ls $LS_OPTIONS -la'
		alias l='ls $LS_OPTIONS'
		set_bash_prompt() {
			fs_mode=$(mount | sed -n -e "s/^\/dev\/.* on \/ .*(\(r[w|o]\).*/\1/p")
			PS1='\[\033[01;32m\]\u@\h${fs_mode:+($fs_mode)}\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
		}
		alias ro='sudo mount -o remount,ro / ; sudo mount -o remount,ro /boot'
		alias rw='sudo mount -o remount,rw / ; sudo mount -o remount,rw /boot'
		PROMPT_COMMAND=set_bash_prompt



