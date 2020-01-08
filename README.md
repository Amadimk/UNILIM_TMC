# Mongoose + ESP8266 + ATEC508 & LoRa + MQTT + Raspberry Pi

# Table of contents

1. [Raspberry Pi & WiFi](#raspwifi)  
  1.1 [Préparation du démarrage bootp, PXE du Raspberry Pi](#preparation)  
         - [Montage de NFS sur le Raspberry Pi](#montage-de-nfs-sur-le-raspberry-pi)  
         - [Activation du service SSH sur le Raspberry PI](#activation-du-service-ssh-sur-le-raspberry-pi)  
         - [Mise en service du serveur TFTP, DNS, DHCP](#mise-en-service)  
  1.2 [Connexion WiFi des ESP8266](#connexion-wifi-des-esp8266)  
2. [Chiffrement ECC : clés et certificats](#chiffrement)  
3. [Communications et sécurité](#communications)  
  3.1 [Raspberry Pi et Esp8266 : WiFi et MQTT](#raspiesp8266)  
  3.2 [Raspberry Pi et Raspberry Pi : LoRa](#raspiraspi)  
4. [Authors](#authors)  
    

Le but de ce projet est de créer un réseau de capteurs (ESP8266) connectés par WiFi vers un concentrateur (un Raspberry Pi) où chaque capteur va exploiter un circuit dédié à la cryptographie sur courbe elliptique (un ATECC508) connecté à l’ESP8266 qui à travers Mongoose publie à intervalle régulier la donnée capturé sur un serveur MQTT securisé par l’utilisation de certificats et du protocole TLS, cette donnée sera ensuite chiffré et transmis  entre deux concentrateurs à travers le protocole LoRa.

![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/intro.png)


<h2 id="raspwifi"> Raspberry Pi & WiFi</h2>

<h3 id="preparation"> Préparation du démarrage bootp, PXE du Raspberry Pi</h3>

Cette partie de la configuration provient des enseignements de Mr PIERRE-FRANCOIS BONNEFOI dans le TP3  de l'UE TMC et est accessible sur son site web : [p-fb.net](https://p-fb.net/master-2/tmc.html?L=0).

* Tout d'abord on crée un repertoire `RASPI` dédié au *«filesystem»* du Raspberry PI  et on crée ensuite deux sous-répertoire : un nommé `client` contenant l’intégralité du système Raspbian du Raspberry ( répertoires `/etc`, `/home`, `/bin`, etc.) qui sera accessible par le protocole NFS qu'on utilisera pour le bootage en mode réseau et un autre nommé `boot` contenant le noyau et les fichiers de *«bas-niveau»* pour le raspberry Pi lui-même, qui sera accessible par le protocole bootp;

```bash
$ mkdir RASPI
$ cd RASPI
$ mkdir client
$ mkdir boot
```

* télécharger la distribution *« Raspbian lite »* sur le site officiel du Raspberry PI et le mettre dans le répertoire RASPI

```bash
$ wget https://downloads.raspberrypi.org/raspbian_lite_latest
$ unzip raspbian_lite_latest

```
* Récupérer le contenu des deux partitions de cette distribution pour remplir les deux sous-répertoires `client` et `boot` :
* Le filesystem raspbian dans le répertoire *« client »* depuis la partion 2 :
```bash
$ sudo losetup -P /dev/loop7 2019-09-26-raspbian-buster-lite.img
$ sudo mount /dev/loop7p2 /mnt
$ mkdir client
$ sudo rsync -xa --progress /mnt/ client/
$ sudo umount /mn

```
* Les fichiers de *« boot »* depuis la partition 1 :
```bash
$ mkdir boot
$ sudo mount /dev/loop7p1 /mnt
$ cp -r /mnt/* boot/

```
* Installer le serveur NFS :
```bash
$ sudo apt install nfs-kernel-server
```

* Configurer le partage NFS dans le fichier `/etc/exports` :
```bash
$ cat /etc/exports
# /etc/exports: the access control list for filesystems which may be exported
# to NFS clients. See exports(5).
#
# Example for NFSv2 and NFSv3:
# /srv/homes hostname1(rw,sync,no_subtree_check)
hostname2(ro,sync,no_subtree_check)
#
# Example for NFSv4:
# /srv/nfs4 gss/krb5i(rw,sync,fsid=0,crossmnt,no_subtree_check)
# /srv/nfs4/homes gss/krb5i(rw,sync,no_subtree_check)

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
* Modifier le point de montage du Raspberry Pi pour son filesystem, en éditant le fichier `RASPI/boot/cmdline.txt`
```bash
$ cat RASPI/boot/cmdline.txt
dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=/dev/nfsnfsroot=10.20.30.1:/home/amadimk/TMC/RASPI/client,vers=3 rw ip=dhcp rootwait elevator=deadline
```
* Ajouter un point de montage qu’utilisera le Raspberry Pi après avoir booté en éditant le fichier  `/RASPI/client/etc/fstab`
```bash
$ cat RASPI/client/etc/fstab
proc            /proc           proc    defaults          0       0
10.20.30.1:/home/amadimk/TMC/RASPI/boot /boot nfs rsize=8192,wsize=8192,timeo=14,intr,noauto,x-systemd.automount   0   0
```
##### Activation du service SSH sur le Raspberry PI
Passer par le point de montage NFS, c-à-d le répertoire local correspondant au filesystem NFS :
```bash
$ cat RASPI/client/lib/systemd/system/sshswitch.service
[Unit]
Description=Turn on SSH if /boot/ssh is present
#ConditionPathExistsGlob=/boot/ssh{,.txt}
After=regenerate_ssh_host_keys.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c "update-rc.d ssh enable && invoke-rc.d ssh start && rm -f/boot/ssh ; rm -f /boot/ssh.txt"

[Install]
```
*Mettre en commentaire la ligne d’option ConditionPathExistsGlob.*

<h4 id="mise-en-service"> Mise en service du serveur TFTP, DNS, DHCP</h4>

* utiliser un script `sh` pour lancer un serveur dhcp et dns avec la commande dnsmasq pour permettre au raspberry de booter une fois connecter à la machine :
```bash
$ cat scriptFile.sh
# dongle ethernet gigabit
IF=enps70
PREFIX=10.20.30
sudo sysctl -w net.ipv4.ip_forward=1
sudo ip link set dev $IF down
sudo ip link set dev $IF up
sudo ip address add dev $IF $PREFIX.1/24
sudo iptables -t nat -A POSTROUTING -s $PREFIX.0/24 -j MASQUERADE
sudo dnsmasq -d -z -i $IF -F $PREFIX.100,$PREFIX.150,255.255.255.0,12h -O 3,$PREFIX.1-O 6,8.8.8.8,8.8.4.4 --pxe -service=0,"Raspberry Pi Boot" --enable-tftp --tftp-root=/home/amadimk/TMC/RASPI/boot
```
### Connexion WiFi des ESP8266

Pour permettre aux capteurs de joindre le concentrateur, il est necessaire de mettre en place un access point wifi sur le Raspberry Pi en installant les paquets hostapd et dnsmasq. Hostapd est un package qui permet de créer un hotspot sans fil à l’aide d’un Raspberry Pi, et dnsmasq quand a lui permet de créer et lancer un serveur DNS et DHCP facilement.
Se connecter en ssh au Raspberry Pi:
```bash
$ ssh pi@10.20.30.149
```
***Remarque :**
*le mot de passe par defaut est : `raspberry`*

```bash
$ sudo apt-get install hostapd
$ sudo apt-get install dnsmasq
```
Une fois les paquets installés on edite les fichiers de configurations de dnsmasq et hostpad pour créer le point d'accès :  

Pour dnsmasq le fichier `/etc/dnsmasq.conf`
```bash
$ sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig        #sauvergader les anciens configs de dnsmasq.
$ sudo nano /etc/dnsmasq.conf                             # creer un nouveau fichier de configuration.
interface=wlan0        #choisir l'interface d'ecoute
dhcp-range=192.168.4.2,192.168.0.20,255.255.255.0,24h
address=/mqtt.com/192.168.4.1       # permettre au dns de faire la resolution d'un domaine ici le mqtt.com
```
***Remarque :**
*la dernière ligne est une option de dnsmasq lui permettant d'associé une adresse IP à un nom symbolique qui sera utile lors de la verification des certificats envoyer par le serveur (Raspberry) au client (ESP8266). 
Configurer le fichier de configuration `/etc/hostapd/hostapd.conf` de hostapd pour créer le point d'accèes.*  

Pour hostapd le fichier `/etc/hostapd/hostapd.conf`
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
Puis editer le fichier `/etc/default/hostapd` pour charger les configurations de hostpad en remplaçant la ligne qui contient DAEMON_CONF par `DAEMON_CONF=”/etc/hostapd/hostapd.conf”`.

Activer le forwarding du noyaux
```bash
$ sudo nano /etc/sysctl.conf

net.ipv4.ip_forward=1        #de-commenter cette ligne.

```
Puis reboot le raspberry.
```bash
$ sudo reboot
```
<h2 id="chiffrement"> Chiffrement ECC : clés et certificats</h2>

Génération des clés privées de L'AC, du serveur et du client.
```bash
$ openssl ecparam -out ecc.ca.key.pem -name prime256v1 -genkey
$ openssl ecparam -out ecc.raspeberry.key.pem -name prime256v1 -genkey
$ openssl ecparam -out ecc.esp8266.key.pem -name prime256v1 -genkey
```
Génération du certificat auto-signé de l'AC qui sera utilisé pour signé ceux du serveur et client
```bash
$ openssl req -config <(printf "[req]\ndistinguished_name=dn\n[dn]\n[ext]\nbasicConstraints=CA:TRUE") -new -nodes -subj "/C=FR/L=Limoges/O=TMC/OU=IOT/CN=ACTMC" -x509 -extensions ext -sha256 -key ecc.ca.key.pem -text -out ecc.ca.cert.pem
```
Génération et signature du certificat pour le serveur (Raspberry Pi)
```bash
$ openssl req -config <(printf "[req]\ndistinguished_name=dn\n[dn]\n[ext]\nbasicConstraints=CA:FALSE") -new -subj   "/C=FR/L=Limoges/O=TMC/OU=IOT/CN=mqtt.com" -reqexts ext -sha256 -key ecc.raspberry.key.pem -text -out ecc.raspberry.csr.pem
$ openssl x509 -req -days 3650 -CA ecc.ca.cert.pem -CAkey ecc.ca.key.pem -CAcreateserial -extfile <(printf   "basicConstraints=critical,CA:FALSE") -in ecc.csr.pem -text -out ecc.respberry.cert.pem -addtrust clientAuth
```

Génération et signature du certificat pour le client (Esp8266)
```bash
$ openssl req -config <(printf "[req]\ndistinguished_name=dn\n[dn]\n[ext]\nbasicConstraints=CA:FALSE") -new -subj   "/C=FR/L=Limoges/O=TMC/OU=IOT/CN=esp8266" -reqexts ext -sha256 -key ecc.esp8266.key.pem -text -out ecc.esp8266.csr.pem
$ openssl x509 -req -days 3650 -CA ecc.ca.cert.pem -CAkey ecc.ca.key.pem -CAcreateserial -extfile <(printf   "basicConstraints=critical,CA:FALSE") -in ecc.esp8266.csr.pem -text -out ecc.esp8266.cert.pem -addtrust clientAuth
```
***Remarque :***
*Les certificats serveur et client doivent être signés par le même CA (Autorité de certification) pour faciliter l'authentification et de plus le "Common Name" **CN** du serveur doit correspondre au nom symbolique de la machine hôte du serveur ici le raspberry Pi : mqtt.com et le certificat du client pour être reconnu par Mongoose OS doit être entouré des lignes exactes :*  
```bash
-----BEGIN CERTIFICATE-----  
...  
-----END CERTIFICATE-----
```

<h2 id="communications">  Communications et sécurité</h2>
<h3 id="raspiesp8266"> Raspberry Pi et Esp8266 : Wifi et MQTT </h3>
L’ESP8266 va se comporter comme un client MQTT qui effectue un **publish** sur le topic `/esp8266` toute les 2 secondes en se connectant au serveur MQTT du Raspberry Pi jouant le rôle de concentrateur et qui fait lui **subscribe** sur le même topic pour récevoir les données.

Pour communiquer le concentrateur et le client utilise le point d'accès wiFi déjâ créer au niveau de ce dernier sur lequel va se connecter le client.  

**Sécurité :** Pour sécuriser les échanges de traffic entre le client et le concentrateur on va s'appuyer sur le protocole **TLS** supporter par le MQTT en utilisant les certificats créer ci-dessus.  
Les configurations à effectués au niveau du concentrateur sont :  
**Installation des paquets du serveur MQTT**
```bash
$ sudo apt-get install mosquitto
$ sudo apt-get install mosquitto-clients
```
**Activer la protection de l'accès au serveur par un mot de passe**  
Pour activer la protection d’accès au serveur MQTT par mot de passe, on ajoute dans le fichier `/etc/mosquitto/mosquitto.conf`
```bash
allow_anonymous false
password_file /etc/mosquitto/mosquitto_passwd
```
Puis utiliser la commande  `mosquitto_passwd` pour créer le contenu du fichier password
```bash
$ sudo mosquitto_passwd -c /etc/mosquitto/mosquitto_passwd mqtt.tmc.com    # oû mqtt.tmc.com est le user
```
**Connexion TLS avec MQTT**  
Pour la connexion par TLS, on ajoute dans le fichier `/etc/mosquitto/mosquitto.conf` :
```bash
listener 8883
cafile /home/pi/NEWCERT/ecc.ca.cert.pem
certfile /home/pi/NEWCERT/ecc.raspi.cert.pem
keyfile /home/pi/NEWCERT/ecc.raspi.key.pem
require_certificate true
```
Puis on redemarre le serveur MQTT pour prendre en compte la configuration effectuée:
```bash
$ sudo service mosquitto restart
```
**Tester la connexion TLS du serveur MQTT**  
Pour effectuer un **publish** 
```bash
$ cd NEWCERT/
$ mosquitto_pub -h mqtt.com -p 8883 -u mqtt.tmc.com -P tmctmctmc -t '/esp8266' --cafile ecc.ca.cert.pem  
--cert ecc.esp8266.cert.pem --key ecc.es8266.key.pem -m 'Hello !'
```
Pour effetcuer **subscribe** 
```bash
$ cd NEWCERT/
$ mosquitto_sub -h mqtt.com -p 8883 -u mqtt.tmc.com -P tmctmctmc -t '/esp8266' --cafile ecc.ca.cert.pem  
--cert ecc.esp8266.cert.pem --key ecc.es8266.key.pem
Hello !
```
Pour la configuration du client ESP8266 on télécharge le système moongose OS pour générer un flash à intégrer dans le composant.  
**Installation de Mongoose OS et d’une application de démonstration**  
Site de l’OS : https://mongoose-os.com
```bash
$ sudo add-apt-repository ppa:mongoose-os/mos
$ sudo apt-get update
$ sudo apt-get install mos
$ mos --help
$ mos
```
Installation de docker avec transfert des droits d’exécution à l’utilisateur indispensable générer un flash :
```bash
$ sudo apt install docker.io
$ sudo groupadd docker
$ sudo usermod -aG docker $USER
```
Installation d’une application de démonstration à adapter pour notre projet :
```bash
$ git clone https://github.com/mongoose-os-apps/empty my-app
```
Pour l’utilisation de MQTT dans Mongoose OS on modifie le fichier `mos.yml` se trouvant dans l'application de démonstration comme suit :
```yaml
$ cd my-app
$ cat mos.yml
author: mongoose-os
description: A Mongoose OS app skeleton
version: 1.0
libs_version: ${mos.version}
modules_version: ${mos.version}
mongoose_os_version: ${mos.version}
# Optional. List of tags for online search.
tags:
- c
# List of files / directories with C sources. No slashes at the end of dir names.
sources:
- src
# List of dirs. Files from these dirs will be copied to the device filesystem
filesystem:
- fs
config_schema:
- ["debug.level", 3]
- ["sys.atca.enable", "b", true, {title: "Activation du composant ATEC508"}]
- ["i2c.enable", "b", true, {title: "Enable I2C"}]
- ["sys.atca.i2c_addr", "i", 0x60, {title: "I2C address of the chip"}]
- ["mqtt.enable", "b", true, {title: "Activation du service MQTT"}]
- ["mqtt.server", "s", "mqtt.com.net:8883", {title: "Adresse du serveur MQTT à joindre"}]
- ["mqtt.pub", "s", "/esp8266", {title: "Le Topic "}]
- ["mqtt.user", "s", "mqtt.tmc.com", {title: "Utilisateur pour acceder au serveur MQTT"}]
- ["mqtt.pass", "s", "tmctmctmc", {title: "Mot de passe du serveur MQTT"}]
- ["mqtt.ssl_ca_cert", "s", "ecc.ca.cert.pem", {title: "Le certificat AC pour verifier le   
certificat du serveur"}]
- ["mqtt.ssl_cert", "s", "ecc.esp8266.cert.pem", {title: "Le certificat du client"}]
- ["mqtt.ssl_key", "ATCA:0"]
cdefs:
MG_ENABLE_MQTT: 1
# List of libraries used by this app, in order of initialisation
libs:
- origin: https://github.com/mongoose-os-libs/ca-bundle
- origin: https://github.com/mongoose-os-libs/rpc-service-config
- origin: https://github.com/mongoose-os-libs/rpc-service-atca
- origin: https://github.com/mongoose-os-libs/rpc-service-fs
- origin: https://github.com/mongoose-os-libs/rpc-mqtt
- origin: https://github.com/mongoose-os-libs/rpc-uart
- origin: https://github.com/mongoose-os-libs/wifi
# Used by the mos tool to catch mos binaries incompatible with this file format
manifest_version: 2017-05-18
```
***Remarque :***
*Le certificat du CA `ecc.ca.cert.pem` et du client `ecc.esp8266.cert.pem` doivent être copiés dans le sous-répertoire  `fs` de l'application correspondant aux fichiers installés dans l’ESP8266.*  
Le code source de l’application Mongoose OS se trouve dans le sous-repertoire `src/main.c`, on le modifie pour l'adapter à notre projet :  
```c
$ cd src
$ cat main.c
#include <stdio.h>
#include "mgos.h"
#include "mgos_mqtt.h"
static void my_timer_cb(void *arg) {
char *message = "Hello i am esp8266 !";
mgos_mqtt_pub("/esp8266", message, strlen(message), 1, 0);
(void) arg;
}
enum mgos_app_init_result mgos_app_init(void) {
mgos_set_timer(2000, MGOS_TIMER_REPEAT, my_timer_cb, NULL);
return MGOS_APP_INIT_SUCCESS;
}
```
**Générer un flash pour l'esp8266 avec Mongoose OS :**  
Pour compiler et générer un flash:
```bash
$ mos build --local --arch esp8266
Warning: --arch is deprecated, use --platform

Firmware saved to /home/amadimk/MASTER2/TMC/PROJET/my-app/build/fw.zip
```
Pour Flasher :
```bash
$  mos flash

Loaded my-app/esp8266 version 1.0 (20200102-195717/2.13.0-ge44f822-master-dirty)
Using port /dev/ttyUSB0
Opening /dev/ttyUSB0 @ 115200...
Connecting to ESP8266 ROM, attempt 1 of 10...
  Connected, chip: ESP8266EX
Running flasher @ 921600...
  Flasher is running
Flash size: 16777216, params: 0x029f (dio,128m,80m)
Deduping...
     2320 @ 0x0 -> 0
   262144 @ 0x8000 -> 4096
   629616 @ 0x100000 -> 0
      128 @ 0xffc000 -> 0
Writing...
     4096 @ 0x7000
     4096 @ 0x10000
     4096 @ 0x3fb000
Wrote 12288 bytes in 0.13 seconds (760.82 KBit/sec)
Verifying...
     2320 @ 0x0
     4096 @ 0x7000
   262144 @ 0x8000
   629616 @ 0x100000
     4096 @ 0x3fb000
      128 @ 0xffc000
Booting firmware...
All done!
```
Pour configurer le composant ESP8266 à se connecter sur le point d'accèes WiFi :
```bash
$ mos wifi raspberryWifi01  Raspberry

Using port /dev/ttyUSB0
Getting configuration...
Setting new configuration...
```
Maintenant il suffit d'installer la clé privée de notre composant dans l’ATECC508 :
```bash
$ openssl rand -hex 32 > slot4.key
$ mos -X atca-set-key 4 slot4.key --dry-run=false

AECC508A rev 0x5000 S/N 0x012352aad1bbf378ee, config is locked, data is locked
Slot 4 is a non-ECC private key slot
SetKey successful.
```
Puis :
```bash
$ mos -X atca-set-key 0 ecc.esp8266.key.pem --write-key=slot4.key --dry-run=false

Using port /dev/ttyUSB0
ATECC508A rev 0x5000 S/N 0x0123fb976eb9b4f3ee, config is locked, data is locked
Slot 0 is a ECC private key slot
Parsed EC PRIVATE KEY
Data zone is locked, will perform encrypted write using slot 4 using slot4.key
SetKey successful.
```
Pour lancer la console mos et voir les activités du composant esp8266 :  
```bash
$ mos console
```
Echange de certificat ESP8266-Raspberry| Connexion MQTT
:-------------------------------------:|:-------------------------------------:
![](https://github.com/Amadimk/UNILIM_TMC/blob/master/mos.png)  |  ![](https://github.com/Amadimk/UNILIM_TMC/blob/master/mqtt.png)

Capture du traffic chiffré entre serveur mosquitto et le client ESP8266|
:-------------------------------------:
![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/tls.png)

<h3 id="raspiraspi"> Raspberry Pi et Raspberry Pi : LoRa </h3>

Le Raspberry Pi qui est configurer avec le serveur MQTT va se comporter comme un client LoRa en récupérant la donnée publier par le composant ESP8266 et l'envoi au second Raspberry Pi qui se comporte comme serveur à travers une communication Radio LoRa.
**Sécurité :** Pour sécuriser les échanges de traffic entre le  Raspberry Pi client et celui serveur on va utiliser un chiffrement **AES-128** puis on utilisera un **Json Web Token (JWT)** chiffré et signé pour l'envoyer au raspberry qui joûe le rôle de serveur.    

Pour utiliser la radio LoRa on  va coiffer nos raspberry Pi d’un dragino, intégrant un « transceiver » LoRa ainsi qu’un GPS.
Le Raspberry Pi et le composant LoRa vont communiquer par l’intermédiaire du bus SPI. qu'on active sur le raspberry.  
**Configuration initiale du Raspberry Pi**  
*La procédure de configuration du Raspberry Pi peut changer suivant la version de votre distribution Raspbian.*
```bash
$ sudo raspi-config
```
Naviguer dans les menus jusqu’à trouver **« Interfacing Options »** puis l’option **« SPI »** à activer.
***Remarque :***
*Une antenne doit toujours être connectée sur le port LoRa, sous peine d’endommager le composant LoRa*  
Mettre à jour le Raspberry Pi
```bash
$ sudo apt-get update
$ sudo apt-get upgrade
$ sudo rpi-update
$ sudo reboot
```
Pour l’utilisation des broches GPIOs et du bus SPI on utilise la bibliothèque bcm2835
```bash
$ wget http://www.airspayce.com/mikem/bcm2835/bcm2835-1.58.tar.gz
$ tar zxvf bcm2835-1.58.tar.gz
$ cd bcm2835-1.58
$ ./configure
$ make
$ sudo make check
$ sudo make install
```
*Pour le bon fonctionnement de la bibliothèque bcm2835 sur Raspberry Pi 3, il faut éditer le fichier
`/boot/config.txt` et ajouter à la fin*
```bash
dtoverlay=gpio-no-irq
```
Pour l’utilisation du LoRa, on utilise la bilbliothèque suivante :
```bash
$ git clone https://github.com/hallard/RadioHead
$ cd RadioHead/examples/raspi/rf95
```
On modifie les deux fichier sources : `rf95_server.cpp` et `rf95_client.cpp` pour
sélectionner le dragino en commentant la ligne qui contient `#define BOARD_LORASPI` et décommenter la ligne contient `//#define BOARD_DRAGINO_PIHAT` ensuite on adapte ces deux fichiers à notre projet pour chiffrer en AES-128 et utiliser le JWT côté client LoRa et faire l'opération inverse côte serveur. Pour ce faire on va écrire un script python coté client et à l'aide des bibliothéques **python-paho-mqtt**, **jwcrypto** et **Crypto** on va pouvoir respectivement créer un client MQTT en **subscribe** utilisant une loop et un callback à la réception d'une donnée publier par le composant ESP8266, créer un JWT token et Chiffrer en AES. A partir du script python on éxecute une command qui lance le programme client LoRa qui lui, est en écrit en langage C++, Il est donc indispensable d'adapter le code C++ pour lui permettre de récupérer le JWT Token en argument.  

**Script python côté client LoRa  :**  
`RadioHead/examples/raspi/rf95/mqtt_client.py`
```python
#!/bin/python3
import paho.mqtt.client as mqtt
import os, ssl, json, binascii, base64, jwt, subprocess
from urllib.parse import urlparse
from Crypto import Random
from Crypto.Cipher import AES

cafile ="/home/pi/NEWCERT/ecc.ca.cert.pem"
cert = "/home/pi/NEWCERT/ecc.raspi.cert.pem"
key = "/home/pi/NEWCERT/ecc.raspi.key.pem"
asymetrickey="/home/pi/NEWCERT/key"

def encrypt(message, passphrase):
    aes = AES.new(passphrase, AES.MODE_CBC, '0123456789123456')
    return base64.b64encode(aes.encrypt(message))

def on_message(client, obj, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    data=encrypt(msg.payload,"tmctmctmctmctmcA")
    command ="./rf95_client "+jwt.encode( {'data':data.decode('utf-8') }, "MQTT", algorithm='HS256').decode('utf-8')
    os.system("%s"%(command))

mqttc = mqtt.Client()

# Assign event callbacks
mqttc.on_message = on_message

url_str = os.environ.get('CLOUDMQTT_URL', 'mqtt://mqtt.com:8883//esp8266')
url = urlparse(url_str)
topic = url.path[1:] or '/esp8266'

# Connect
mqttc.username_pw_set("mqtt.tmc.com", "tmctmctmc")
mqttc.tls_set(ca_certs=cafile, certfile=cert, keyfile=key, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS, ciphers=None)
mqttc.connect(url.hostname, url.port)

# Start subscribe, with QoS level 0
mqttc.subscribe(topic, 0)

rc = 0
while rc == 0:
    rc = mqttc.loop()
```
Pour adapter le programme client LoRa `C++` il suffit de remplacer la partie de l'envoi du message par :
`RadioHead/examples/raspi/rf95/rf95_client.cpp`
```cpp
.....
 // Send a message to rf95_server
 const char* msg1;
 std::string str = argv[1];  // On récupére l'argument du programme
 msg1 = str.c_str();
 size_t length = strlen(msg1) + 1;
	
 const char* beg = msg1;
 const char* end = msg1 + length;
 uint8_t* msg2 = new uint8_t[length];
 
 size_t i = 0;
 for (; beg != end; ++beg, ++i){
   msg2[i] = (uint8_t)(*beg);
 }
 uint8_t data[] = "hi";
 uint8_t len = sizeof(data);
 
 printf("Sending %02d bytes to node #%d => ", len, RF_GATEWAY_ID );
 printbuffer(msg2, length);
 printf("\n" );
 rf95.send(msg2, length);
 rf95.waitPacketSent();
 exit(1);
 ......
```
Côté serveur LoRa on écrit aussi un script en python récevant en argument un JWT, le décode et déchiffre l'AES avec une clé partagée avec le client. Le script python sera éxecuté par le programme serveur LoRa `C++` à la réception de chaque paquets LoRa, il est donc indispensable comme pour le client LoRa de modifier le programme serveur.

**Script python côté serveur LoRa  :**  
`RadioHead/examples/raspi/rf95/mqtt_decrypt.py`
```python
#!/bin/python3
import jwt, subprocess, sys, binascii,os, ssl, base64
from Crypto.Cipher import AES

data = sys.argv[1]
print("Receive JWT token : " +data)
encoded=""
try:
        encoded = jwt.decode(data, "MQTT")
        print("Decoded JWT data (encoded base64 + AES ) : " + encoded['data'])
except:
        print("Erreur decode JWT")
        exit(1)
        
decryption_suite = AES.new('tmctmctmctmctmcA', AES.MODE_CBC, '0123456789123456')
try:
        plain_text = decryption_suite.decrypt(base64.b64decode(encoded['data']))
        print("Decoded AES data : " + plain_text.decode('utf-8'))
except:
        print("Erreur AES decrypt")
        exit(1)
```
Pour la modification du programme serveur LoRa on remplace dans la partie receive du code par celui ci-dessous :
`RadioHead/examples/raspi/rf95/rf95_serveur.cpp`
```cpp
.....
if (rf95.recv(buf, &len)) {
  printf("Packet[%02d] #%d => #%d %ddB: \n", len, from, to, rssi);
  printbuffer(buf, len);
  printf("\n");
  std::string convert;
  convert.assign(buf, buf+len);

  char buffer[512];
  std::string result = "";
  std::string str = "python3 mqtt_decrypt.py \""+convert+"\"";
  const char * command = str.c_str();
  FILE* pipe = popen(command, "r");
	 if (!pipe) throw std::runtime_error("popen() failed!");
  try {
        while (fgets(buffer, sizeof buffer, pipe) != NULL) {
             result += buffer;
             }
       } catch (std::string const& chaine){
       pclose(pipe);
       throw;
     }
     std::cout << result << std::endl;
     pclose(pipe);
     } else {
      Serial.print("receive failed");
      }
      printf("\n");
.....
```
**Compiler et tester**  
Pour Compiler :
```cpp
$ make
```
lancer le programme serveur LoRa
```bash
$ sudo ./rf95_server
```
Réception du token JWT et déchiffrement coté serveur LoRa|
:-------------------------------------:
![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/serveur.png)

lancer le programme client LoRa
```bash
$ sudo python3 mqtt_client.py
```
Chiffrement du message avec AES et envoi du token JWT|
:-------------------------------------:
![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/Client.png)

## Démo

## Authors

* **Amadou Oury DIALLO**  - [Github](https://github.com/Amadimk)
* **Moetaz RABAI** - [Github](https://github.com/Jalix07)
* **Wajdi KILANI** - [Github](https://github.com/kilanix)

