import json
import os
from pprint import pprint

from Services.Engine import Engine


telegram_access_token = os.environ.get('telegram_access_token')
etherscan_api_token = os.environ.get('etherscan_access_token')

engine = Engine(telegram_access_token, etherscan_api_token)
engine.start_loop()

