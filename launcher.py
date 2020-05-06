import json
import os
from pprint import pprint

from Services.Engine import Engine


access_token = os.environ.get('telegram_access_token')
engine = Engine(access_token)
engine.launch_hook('176.57.71.32:443')
# engine.launch_long_polling()

