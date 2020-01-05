 # Mongoose + ESP8266 + ATEC508 & LoRa + MQTT + Raspberry Pi

Le but de ce projet est de créer un réseau de capteurs (ESP8266) connectés par WiFi vers un concentrateur (un Raspberry Pi) où chaque capteur va exploiter un circuit dédié à la cryptographie (un ATECC508) connecté à l’ESP8266 qui à travers Mongoose publie à intervalle régulier la donnée capturé sur un serveur MQTT securisé par l’utilisation de certificats et du protocole TLS, cette donnée sera ensuite chiffré et transmis  entre deux concentrateurs à travers le protocole LoRa.

![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/intro.png)


## Raspberry Pi & WiFi

### Préparation du démarrage bootp, PXE du Raspberry Pi

Cette partie de la configuration provient des enseignements de Mr PIERRE-FRANCOIS BONNEFOI dans le TP3  de l'UE TMC et est accessible sur son site web : [p-fb.net](https://p-fb.net/master-2/tmc.html?L=0).

* Tout d'abord on crée un repertoire RASPI dédié au «filesystem» du Raspberry PI  et on crée ensuite deux sous-répertoire : un client contenant l’intégralité du système Raspbian du Raspberry (répertoires /etc, /home, /bin, etc.) qui sera accessible par le protocole NFS qu'on utilisera pour le boot et un autre boot contenant le noyau et les fichiers de «bas-niveau» pour le raspberry Pi lui-même, qui sera accessible par le protocole bootp;

```bash
$ mkdir RASPI
$ cd RASPI
$ mkdir client
$ mkdir boot
```

* télécharger la distribution « Raspbian lite » sur le site officiel du Raspberry PI et le mettre dans le répertoire RASPI

```bash
$ wget https://downloads.raspberrypi.org/raspbian_lite_latest
$ unzip raspbian_lite_latest

```
* Récupérer le contenu des deux partitions de cette distribution pour remplir les deux sous-répertoires client et boot :
* Le filesystem raspbian dans le répertoire « client » depuis la partion 2 :

```bash
$ sudo losetup -P /dev/loop7 2019-09-26-raspbian-buster-lite.img
$ sudo mount /dev/loop7p2 /mnt
$ mkdir client
$ sudo rsync -xa --progress /mnt/ client/
$ sudo umount /mn

```
* Les fichiers de « boot » depuis la partition 1 :

```bash
$ mkdir boot
$ sudo mount /dev/loop7p1 /mnt
$ cp -r /mnt/* boot/

```
* Installer le serveur NFS :
```bash
$ sudo apt install nfs-kernel-server
```

* Configurer le partage NFS dans le fichier /etc/exports :
```bash
.....................
/home/amadimk/TMC/RASPI/client *(rw,sync,no_subtree_check,no_root_squash)
/home/amadimk/TMC/RASPI/boot *(rw,sync,no_subtree_check,no_root_squash)
```
* Activer le service NFS et RPCBind :

```bash
$ sudo systemctl enable nfs-kernel-server
$ sudo systemctl enable rpcbind
```
* Ensuite il faut redémarrer le service NFS pour prendre en charge la nouvelle configuration :
```bash
$ sudo systemctl restart nfs-kernel-server
```
* Pour voir les points de montage offert par un serveur NFS :
```bash
$ showmount -e 127.0.0.1
Export list for 127.0.0.1:
/home/amadimk/TMC/RASPI/boot   *
/home/amadimk/TMC/RASPI/client *
```
##### Montage de NFS sur le Raspberry Pi
* Modifier le point de montage du Raspberry Pi pour son filesystem, en éditant le fichier  
/RASPI/boot/cmdline.txt
```
dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=/dev/nfsnfsroot=10.20.30.1:/home/amadimk/TMC/RASPI/client,vers=3 rw ip=dhcp rootwait elevator=deadline
```
* Ajouter un point de montage qu’utilisera le Raspberry Pi après avoir booté en éditant le fichier  
/RASPI/client/etc/fstab
```
10.20.30.1:/home/amadimk/TMC/RASPI/boot /boot nfs rsize=8192,wsize=8192,timeo=14,intr,noauto,x-systemd.automount   0   0
```
##### Activation du service SSH sur le Raspberry PI
Passer par le point de montage NFS, c-à-d le répertoire local correspondant au filesystem NFS :
```
amadimk@pc:~/TMC/RASPI/client/lib/systemd/system$ cat sshswitch.service
[Unit]
Description=Turn on SSH if /boot/ssh is present
#ConditionPathExistsGlob=/boot/ssh{,.txt}
After=regenerate_ssh_host_keys.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c "update-rc.d ssh enable && invoke-rc.d ssh start && rm -f/boot/ssh ; rm -f /boot/ssh.txt"

[Install]
```
Mettre en commentaire la ligne d’option ConditionPathExistsGlob.
##### Mise en service du serveur TFTP, DNS, DHCP

* utiliser un script sh pour lancer un serveur dhcp et dns avec la commande dnsmasq pour permettre au raspberry de booter une fois connecter à la machine :
```bash
# dongle ethernet gigabit
IF=enps70

PREFIX=10.20.30
sudo sysctl -w net.ipv4.ip_forward=1
sudo ip link set dev $IF down
sudo ip link set dev $IF up
sudo ip address add dev $IF $PREFIX.1/24
sudo iptables -t nat -A POSTROUTING -s $PREFIX.0/24 -j MASQUERADE
sudo dnsmasq -d -z -i $IF -F $PREFIX.100,$PREFIX.150,255.255.255.0,12h -O 3,$PREFIX.1-O 6,8.8.8.8,8.8.4.4 --pxe
-service=0,"Raspberry Pi Boot" --enable-tftp --tftp-root=/home/amadimk/TMC/RASPI/boot
```
### Connexion WiFi des ESP8266

Pour permettre aux capteurs de joindre le concentrateur, il est necessaire de mettre en place un access point wifi sur le Raspberry Pi en installant les paquets hostapd et dnsmasq. Hostapd est un package qui permet de créer un hotspot sans fil à l’aide d’un Raspberry Pi, et dnsmasq quand a lui permet de créer et lancer un serveur DNS et DHCP facilement.
```bash
$ sudo apt-get install hostapd
$ sudo apt-get install dnsmasq
```
Une fois les paquets installés on edite les fichiers de configurations de dnsmasq et hostpad pour créer le point d'accès :  
/etc/dnsmasq.conf
```bash
$ sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
$ sudo nano /etc/dnsmasq.conf

interface=wlan0        #choisir l'interface d'ecoute
dhcp-range=192.168.4.2,192.168.0.20,255.255.255.0,24h
address=/mqtt.com/192.168.4.1       # permettre au dns de faire la resolution d'un domaine ici le mqtt.com
```
/etc/hostapd/hostapd.conf
```bash
$ sudo nano /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=raspberryWifi01
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=Raspberry01
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

Puis editer le fichier /etc/default/hostapd pour charger les configurations de hostpad 
```bash
$ sudo nano /etc/default/hostapd

 DAEMON_CONF=”/etc/hostapd/hostapd.conf” #modifier cette ligne comme suit

```
Activer le forwarding du noyaux
```bash
$ sudo nano /etc/default/hostapd
$ sudo nano /etc/sysctl.conf

net.ipv4.ip_forward=1        #modifier cette ligne comme suit

```
Puis reboot le raspberry
```bash
$ sudo reboot
```


### Authors

* **Amadou Oury DIALLO** - *Initial work* - [PurpleBooth](https://github.com/Amadimk)
* **Moetaz RABAI** - *Initial work* - [PurpleBooth](https://github.com/Jalix07)
* **Wajdi KILANI** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)

