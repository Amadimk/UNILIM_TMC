IF=enp7s0

PREFIX=10.20.31
sudo sysctl -w net.ipv4.ip_forward=1
sudo ip link set dev $IF down
sudo ip link set dev $IF up
sudo ip address add dev $IF $PREFIX.1/24
sudo iptables -t nat -A POSTROUTING -s $PREFIX.0/24 -j MASQUERADE
sudo dnsmasq -d -z -i $IF -F $PREFIX.100,$PREFIX.150,255.255.255.0,12h -O 3,$PREFIX.1 -O 6,8.8.8.8,8.8.4.4 --pxe-service=0,"Raspberry Pi Boot" --enable-tftp --tftp-root=/home/amadimk/MASTER2/TMC/PROJET/RASPI/boot
