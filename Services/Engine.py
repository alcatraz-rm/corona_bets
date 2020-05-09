import requests
import logging
from datetime import datetime, date, timedelta
import os
import platform
import json
import signal
import time
import tornado.web, tornado.escape, tornado.ioloop

import threading
from queue import Queue

from pprint import pprint

from Services.CommandHandler import CommandHandler
from Services.EventParser import EventParser
from Services.DataKeeper import DataKeeper
from Services.Sender import Sender
from Services.EtherScan import EtherScan

from Services.Handler import Handler


class Engine:
    def __init__(self, access_token):
        self._logger = logging.getLogger('Engine')
        self._configure_logger()

        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'

        self._command_handler = CommandHandler(self._access_token)
        self._event_parser = EventParser()
        self._ether_scan = EtherScan()
        self._sender = Sender(self._access_token)
        self._data_keeper = DataKeeper()
        self._data_keeper.update()

        self._application = tornado.web.Application([
            (r"/",
             Handler,
             dict(data_keeper=self._data_keeper, command_handler=self._command_handler, sender=self._sender)),
        ])

        self._updates_queue = Queue()
        self._lock = threading.Lock()
        self._finish = False

        self._logger.info('Engine initialized.')

    def _configure_logger(self):
        self._logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("log.log", "w", "utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(fh)

        self._logger.info(f'Platform: {platform.system().lower()}')
        self._logger.info(f'WD: {os.getcwd()}')

    def _get_updates(self, offset=None, timeout=10):
        return requests.get(self._requests_url + 'getUpdates',
                            {'timeout': timeout, 'offset': offset}).json()['result']

    def _log_update(self, update):
        log_message = {}

        if 'message' in update:

            log_message['type'] = 'message'

            chat_id = update['message']['from']['id']
            log_message['from'] = {'chat_id': chat_id}

            if 'last_name' in update['message']['from']:
                name = f"{update['message']['from']['first_name']} {update['message']['from']['last_name']}"
            else:
                name = f"{update['message']['from']['first_name']}"

            log_message['from']['name'] = name

            if 'username' in update['message']['from']:
                log_message['from']['username'] = update['message']['from']['username']

            log_message['text'] = update['message']['text']
            log_message['update_id'] = update['update_id']

        elif 'callback_query' in update:
            log_message['type'] = 'callback_query'
            log_message['from'] = {'chat_id':  update['callback_query']['from']['id']}

            if 'last_name' in update['callback_query']['from']:
                name = f"{update['callback_query']['from']['first_name']} " \
                       f"{update['callback_query']['from']['last_name']}"
            else:
                name = f"{update['callback_query']['from']['first_name']}"

            log_message['from']['name'] = name

            if 'username' in update['callback_query']['from']:
                log_message['from']['username'] = update['callback_query']['from']['username']

            log_message['update_id'] = update['update_id']
            log_message['callback_query_id'] = update['callback_query']['id']
            log_message['data'] = update['callback_query']['data']

        else:
            log_message = update

        self._logger.info(f'New update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def launch_long_polling(self):
        self._logger.info('Launching long polling...')

        new_offset = None

        try:
            while True:
                updates = self._get_updates(new_offset)
                for update in updates:
                    # pprint(update)

                    self._log_update(update)

                    if update:
                        if 'message' in update:
                            chat_id = update['message']['from']['id']

                            if self._data_keeper.is_new_user(update):
                                self._data_keeper.add_user(update)

                            last_update_id = update['update_id']

                            if update['message']['text'].startswith('/'):
                                self._command_handler.handle_command(update)
                            else:
                                self._command_handler.handle_text_message(update)

                            new_offset = last_update_id + 1

                        elif 'callback_query' in update:
                            last_update_id = update['update_id']
                            chat_id = update['callback_query']['from']['id']
                            state = self._data_keeper.get_state(chat_id)

                            if state:
                                self._command_handler.handle_state(chat_id, state, update)
                            else:
                                self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

                            new_offset = last_update_id + 1

        except KeyboardInterrupt:
            self._logger.info('Keyboard interrupt occurred. Quit.')
            exit(0)

    def launch_long_polling_threads(self):
        self._logger.info('Launching long polling with 2 threads...')

        try:
            self._finish = False
            listening_thread = threading.Thread(target=self._listen, daemon=True)
            handling_thread = threading.Thread(target=self._handle, daemon=True)
            listening_thread.start()
            handling_thread.start()

            listening_thread.join()
            handling_thread.join()
        except KeyboardInterrupt:
            print('Keyboard interrupt. Quit.')

    def process(self):
        self._configure_first_time()

        listening_thread = threading.Thread(target=self._listen, daemon=True)
        handling_thread = threading.Thread(target=self._handle, daemon=True)

        listening_thread.start()
        handling_thread.start()

        time_limit = self._data_keeper.get_time_limit()

        while True:
            remaining_time = (time_limit - datetime.utcnow()).total_seconds()

            if remaining_time <= 0:
                with self._lock:
                    self._finish = True
                break

            if remaining_time // 2 > 10:
                time.sleep(remaining_time // 2)
            else:
                time.sleep(10)

        listening_thread.join()
        handling_thread.join()

        self._broadcast_time_limit_message()

        listening_thread = threading.Thread(target=self._listen, daemon=True)
        handling_thread = threading.Thread(target=self._handle, daemon=True)

        listening_thread.start()
        handling_thread.start()

        # start new threads for handling messages, but bets is NOT ALLOWED

        # wait results, when event happened - broadcast message with results and send money
        # configure for new round, broadcast message about new round and go to next iteration

    def _configure_new_round(self, control_value):
        self._data_keeper.reset_users()

        self._data_keeper.update_control_value(control_value)
        self._data_keeper.set_time_limit('new time limit')

    def _broadcast_time_limit_message(self):
        users = self._data_keeper.get_users(None)
        timeout_message = self._data_keeper.responses['40']

        for user in users:
            lang = user['lang']

            self._sender.send(user['chat_id'], timeout_message[lang]
                              .replace('{#1}', str(self._data_keeper.get_rate_A())))\
                              .replace('{#2}', str(self._data_keeper.get_rate_B()))

    def _configure_first_time(self):
        wallet_A = input('wallet A: ')

        while not self._ether_scan.wallet_is_correct(wallet_A):
            wallet_A = input('Incorrect wallet, please retry')

        wallet_B = input('wallet B: ')

        while not self._ether_scan.wallet_is_correct(wallet_B):
            wallet_B = input('Incorrect wallet, please retry')

        control_value = self._event_parser.update()['day']
        answer = input(f'Use {control_value} as control value? (y/n)')

        if answer == 'y':
            self._data_keeper.set_control_value(control_value)
        else:
            control_value = int(input('enter the control value: '))
            self._data_keeper.set_control_value(control_value)

        bet_amount = self._data_keeper.get_bet_amount()
        answer = input(f'Use {bet_amount} as bet amount? (y/n)')

        if answer == 'y':
            self._data_keeper.set_bet_amount(bet_amount)
        else:
            bet_amount = int(input('enter the bet amount: '))
            self._data_keeper.set_bet_amount(bet_amount)

        fee = int(input('enter the fee: '))
        self._data_keeper.set_fee(fee)

        now = datetime.utcnow()
        day, month, year = now.day, now.month, now.year
        tomorrow = date(year, month, day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)
        self._data_keeper.set_time_limit(time_limit)

        self._finish = False

        self._logger.info('Configured.')

    def _listen(self):
        new_offset = None

        while True:
            with self._lock:
                if self._finish:
                    break

            updates = self._get_updates(new_offset)

            for update in updates:
                self._log_update(update)
                print('write new update to queue')
                last_update_id = update['update_id']

                with self._lock:
                    self._updates_queue.put(update)

                new_offset = last_update_id + 1

    def _handle(self, allow_bets=True):
        while True:
            with self._lock:
                if self._finish:
                    break

            update = None
            with self._lock:
                if not self._updates_queue.empty():
                    update = self._updates_queue.get()

            if update:
                print('start handling new update')

                if 'message' in update:
                    if self._data_keeper.is_new_user(update):
                        self._data_keeper.add_user(update)

                    if update['message']['text'].startswith('/'):
                        self._command_handler.handle_command(update, allow_bets)
                    else:
                        self._command_handler.handle_text_message(update)

                elif 'callback_query' in update:
                    chat_id = update['callback_query']['from']['id']
                    state = self._data_keeper.get_state(chat_id)

                    if state:
                        self._command_handler.handle_state(chat_id, state, update)
                    else:
                        self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

                print('end handling new update')

    def launch_hook(self, address):
        self._logger.info('Launching webhook...')
        self._logger.debug(address)

        # with open('/etc/letsencrypt/live/vm1139999.hl.had.pm/fullchain.pem', 'r', encoding='utf-8') as cert:
        #     cert_data = cert.read()

        signal.signal(signal.SIGTERM, self._signal_term_handler)

        try:
            print(self._requests_url + "setWebhook?url=%s" % address)
            cert_file = '@/etc/letsencrypt/live/vm1139999.hl.had.pm/fullchain.pem'

            set_hook = requests.get(self._requests_url + "setWebhook", params={'url': address, 'certificate': cert_file})
            # set_hook = requests.get(self._requests_url + "setWebhook?url=%s" % address)
            pprint(set_hook.json())
            self._logger.debug(set_hook.json())

            if set_hook.status_code != 200:
                self._logger.error(f"Can't set hook to address: {address}")
                exit(1)

            self._logger.info('Start listening...')

            self._application.listen(port=443, address='')
            tornado.ioloop.IOLoop.current().start()

        except KeyboardInterrupt:
            self._logger.info('Keyboard interrupt occurred. Deleting webhook...')
            self._signal_term_handler(signal.SIGTERM, None)

    def _signal_term_handler(self, signum, frame):
        response = requests.post(self._requests_url + "deleteWebhook")
        self._logger.debug(response.json())
        self._logger.info('Webhook was successfully deleted.')
