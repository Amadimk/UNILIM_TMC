 # Mongoose + ESP8266 + ATEC508 & LoRa + MQTT + Raspberry Pi

Le but de ce projet est de créer un réseau de capteurs (ESP8266) connectés par WiFi vers un concentrateur (un Raspberry Pi) où chaque capteur va exploiter un circuit dédié à la cryptographie (un ATECC508) connecté à l’ESP8266 qui à travers Mongoose publie à intervalle régulier la donnée capturé sur un serveur MQTT securisé par l’utilisation de certificats et du protocole TLS, cette donnée sera ensuite chiffré et transmis  entre deux concentrateurs à travers le protocole LoRa.

![alt text](https://github.com/Amadimk/UNILIM_TMC/blob/master/intro.png)


## Raspberry Pi & WiFi

#### Préparation du démarrage bootp, PXE du Raspberry Pi

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
* Le filesystem raspbian dans le répertoireclientdepuis la partion nº2 :

```bash
$ sudo losetup -P /dev/loop7 2019-09-26-raspbian-buster-lite.img
$ sudo mount /dev/loop7p2 /mnt
$ mkdir client
$ sudo rsync -xa --progress /mnt/ client/
$ sudo umount /mn

```
* Les fichiers de « boot » depuis la partition nº1 :

```bash
$ mkdir boot
$ sudo mount /dev/loop7p1 /mnt
$ cp -r /mnt/* boot/

```
* Nous installerons le serveur NFS :
```bash
$ sudo apt install nfs-kernel-server

```
* Configurer du partage NFS dans le fichier/etc/exports:
```bash
pef@cube:/etc$ cat exports
# /etc/exports: the access control list for filesystems which may be exported
#to NFS clients.  See exports(5).
#
# Example for NFSv2 and NFSv3:
# /srv/homeshostname1(rw,sync,no_subtree_check)
hostname2(ro,sync,no_subtree_check
#
# Example for NFSv4:
# /srv/nfs4gss/krb5i(rw,sync,fsid=0,crossmnt,no_subtree_check)
# /srv/nfs4/homes  gss/krb5i(rw,sync,no_subtree_check)
#
/home/pef/RASPI/client *(rw,sync,no_subtree_check,no_root_squash)
/home/pef/RASPI/boot *(rw,sync,no_subtree_check,no_root_squash)
```
* Activer le service NFS et RPCBind :

```bash
$ sudo systemctl enable nfs-kernel-server
$ sudo systemctl enable rpcbind
```
* Ensuite il faut redémarrer le service NFS parce que nous avons modifié la configuration d’un export :
```bash
$ sudo systemctl restart nfs-kernel-server

```
* Pour voir les points de montage offert par un serveur NFS :

```bash
$ showmount -e 127.0.0.1
Export list for 127.0.0.1:
/home/pef/RASPI/boot   *
/home/pef/RASPI/client *

```
#### Mise en service du serveur TFTP, DNS, DHCP
* On va utiliser la commande dnsmasq:

```bash
# dongle ethernet gigabit
IF=enx000ec6885a80
#adaptateur USB C
#IF=enx4ce17347b17e

PREFIX=10.20.30
sudo sysctl -w net.ipv4.ip_forward=1
sudo ip link set dev $IF down
sudo ip link set dev $IF address aa:aa:aa:aa:aa:aa
sudo ip link set dev $IF up
sudo ip address add dev $IF $PREFIX.1/24
sudo iptables -t nat -A POSTROUTING -s $PREFIX.0/24 -j MASQUERADE
sudo dnsmasq -d -z -i $IF -F $PREFIX.100,$PREFIX.150,255.255.255.0,12h -O 3,$PREFIX.1-O 6,8.8.8.8,8.8.4.4 --pxe
-service=0,"Raspberry Pi Boot" --enable-tftp --tftp-root=$HOME/RASPI/boot

```
#### Montage de NFS sur le Raspberry Pi
* Modifier le point de montage du Raspberry Pi pour son filesystem, en éditant le fichier  
/RASPI/boot/cmdline.txt
```
dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=/dev/nfsnfsroot=10.20.30.1:/home/pef/RASPI/client,vers=3 rw ip=dhcp rootwait elevator=deadline
```
* Ajouter un point de montage qu’utilisera le Raspberry Pi après avoir booté en éditant le fichier  
/RASPI/client/etc/fstab
```
10.20.30.1:/home/pef/RASPI/boot /boot nfs rsize=8192,wsize=8192,timeo=14,intr,noauto,x-systemd.automount   0   0

```
#### Activation du service SSH sur le Raspberry PI
Passer par le point de montage NFS, c-à-d le répertoire local correspondant au filesystem NFS :
```
pef@cube:~/RASPI/client/lib/systemd/system$ cat sshswitch.service
[Unit]
Description=Turn on SSH if /boot/ssh is present
#ConditionPathExistsGlob=/boot/ssh{,.txt}
After=regenerate_ssh_host_keys.service


[Service]
Type=oneshot
ExecStart=/bin/sh -c "update-rc.d ssh enable && invoke-rc.d ssh start && rm -f/boot/ssh ; rm -f /boot/ssh.txt"

[Install]
```
* Mettre en commentaire la ligne d’optionConditionPathExistsGlob.
## Authors

* **Amadou Oury DIALLO** - *Initial work* - [PurpleBooth](https://github.com/Amadimk)
* **Moetaz RABAI** - *Initial work* - [PurpleBooth](https://github.com/Jalix07)
* **Wajdi KILANI** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)


### Prerequisites

What things you need to install the software and how to install them

```
Give examples
```

### Installing

A step by step series of examples that tell you how to get a development env running

Say what the step will be

```
Give the example
```

And repeat

```
until finished
```

End with an example of getting some data out of the system or using it for a little demo

## Running the tests

Explain how to run the automated tests for this system

### Break down into end to end tests

Explain what these tests test and why

```
Give an example
```

### And coding style tests

Explain what these tests test and why

```
Give an example
```

## Deployment

Add additional notes about how to deploy this on a live system

## Built With

* [Dropwizard](http://www.dropwizard.io/1.0.2/docs/) - The web framework used
* [Maven](https://maven.apache.org/) - Dependency Management
* [ROME](https://rometools.github.io/rome/) - Used to generate RSS Feeds

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags). 



## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Hat tip to anyone whose code was used
* Inspiration
* etc

