#!/bin/python3
import jwt, subprocess
import paho.mqtt.client as mqtt
import os
import ssl
from urllib.parse import urlparse
from jwcrypto import jwk, jwe
from jwcrypto.common import json_encode
import json
import binascii
from Crypto import Random
from Crypto.Cipher import AES
import base64

cafile ="/home/pi/NEWCERT/ecc.ca.cert.pem"
cert = "/home/pi/NEWCERT/ecc.raspi.cert.pem"
key = "/home/pi/NEWCERT/ecc.raspi.key.pem"
asymetrickey="/home/pi/NEWCERT/key"



def encrypt(message, passphrase):
    aes = AES.new(passphrase, AES.MODE_CBC, '0123456789123456')
    return base64.b64encode(aes.encrypt(message))

def on_message(client, obj, msg):
    print("Receive from topic "+msg.topic + " ==> " + msg.payload.decode('utf-8'))
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
k
