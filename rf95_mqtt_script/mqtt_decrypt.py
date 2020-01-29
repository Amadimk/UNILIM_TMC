#!/bin/python3
import jwt, subprocess, sys
import os
import ssl
from urllib.parse import urlparse
from jwcrypto import jwk, jwe
from jwcrypto.common import json_encode
import binascii
from Crypto.Cipher import AES
import base64

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
