import json

from Services.Engine import Engine

with open('auth.json', 'r', encoding='utf-8') as auth_file:
    data = json.load(auth_file)

engine = Engine(data['access_token'], data['api_token_etherscan'])
engine.launch_long_polling()
