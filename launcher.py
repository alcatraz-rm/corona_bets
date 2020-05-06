import json
import os
from pprint import pprint

from Services.Engine import Engine


access_token = os.environ.get('telegram_access_token')
engine = Engine(access_token)
engine.launch_hook('http://dc46e521.ngrok.io')
# engine.launch_long_polling()

