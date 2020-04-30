import json

from Engine import Engine

with open('auth.json', 'r', encoding='utf-8') as auth_file:
    token = json.load(auth_file)['access_token']

engine = Engine(token)
engine.launch_long_polling()
