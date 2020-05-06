import json
import os
from pprint import pprint

from Services.Engine import Engine


with open('auth.json', 'r', encoding='utf-8') as auth_file:
    data = json.load(auth_file)

access_token = os.environ.get('telegram_access_token')
engine = Engine(access_token)
engine.launch_hook('vm1139999.hl.had.pm')
# engine.launch_long_polling()

