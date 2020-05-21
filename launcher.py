import json
import os
from pprint import pprint

from Services.Engine import Engine


access_token = os.environ.get('telegram_access_token')
engine = Engine(access_token)
# engine.launch_hook('https://vm1139999.hl.had.pm:443')
# engine.launch_long_polling_threads()
engine.start_loop()

