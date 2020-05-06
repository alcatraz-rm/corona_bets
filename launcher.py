import json
import os
from pprint import pprint
import chardet

from Services.Engine import Engine


# access_token = os.environ.get('telegram_access_token')
# engine = Engine(access_token)
# engine.launch_hook('https://vm1139999.hl.had.pm')
# engine.launch_long_polling()

import socket

sock = socket.socket()
sock.bind(('', 443))
sock.listen(1)
conn, addr = sock.accept()

print('connected: ', addr)

while True:
    data = conn.recv(1024)
    print(chardet.detect(data))
    print(data.decode(encoding='utf-8'))
    if not data:
        break
    conn.send(data.upper())

conn.close()

