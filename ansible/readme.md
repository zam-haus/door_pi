# Usage (run as root):
* configure raspi image file (add ssh file in boot partition and add ssh public key to authorized keys file for root and pi user):

		ansible-playbook setup-rpi-image.yml -e file=/home/USER/Downloads/2022-01-28-raspios-bullseye-arm64-lite.img -e key=/home/USER/.ssh/id_rsa.pub
Note: /dev/loop0 is used as hard-coded loopback device

* write disk image to sdcard:

		dd if=/home/USER/Downloads/2022-01-28-raspios-bullseye-arm64-lite.img of=/dev/DISK status=progress

* configure read only root

		ansible-playbook setup-rpi-readonly.yml -i IP, -e hostname=HOSTNAME
Note: the extra comma at the end is not a mistake

