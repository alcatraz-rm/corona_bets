import json
import logging
import os
import platform
import threading
import time
from datetime import datetime, date, timedelta
from queue import Queue

import requests

from Services.CommandHandler import CommandHandler
from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.EventParser import EventParser
from Services.Sender import Sender


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

        self._data_storage = DataStorage()
        self._data_storage.update_statistics()

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

    def _get_updates(self, offset=None, timeout=30):  # try to change timeout
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
            log_message['from'] = {'chat_id': update['callback_query']['from']['id']}

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

        self._logger.info(f'New update_statistics: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

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

        while True:
            listening_thread = threading.Thread(target=self._listen, daemon=True)
            handling_thread = threading.Thread(target=self._handle, daemon=True)
            verify_bets_thread = threading.Thread(target=self._confirming_bets, daemon=True)

            listening_thread.start()
            handling_thread.start()
            verify_bets_thread.start()

            self._logger.debug('Start listening, handling and bets verifying thread threads.')

            time_limit = self._data_storage.time_limit

            self._logger.debug(f'time limit: {time_limit}')

            while True:
                remaining_time = (time_limit - datetime.utcnow()).total_seconds()

                if remaining_time <= 5:
                    with self._lock:
                        self._finish = True
                    break

                if remaining_time // 2 > 3:
                    time.sleep(remaining_time // 2)
                else:
                    time.sleep(3)

            listening_thread.join()
            handling_thread.join()

            self._logger.debug('Listening and handling threads joined.')

            self._broadcast_time_limit_message()

            listening_thread = threading.Thread(target=self._listen, daemon=True)
            handling_thread = threading.Thread(target=self._handle, args=(False,), daemon=True)

            self._finish = False

            listening_thread.start()
            handling_thread.start()

            self._logger.debug('Start listening and handling threads (bets are not allowed).')

            old_date_update = self._event_parser.update()['date']

            while True:
                date_ = self._event_parser.update()['date']

                if date_ != old_date_update:
                    self._finish = True
                    break

                time.sleep(300)
            # time.sleep(60)  # for test
            # self._finish = True  # for test

            listening_thread.join()
            handling_thread.join()

            self._logger.debug('listening and handling threads (bets are not allowed) joined')

            value = self._event_parser.update()['day']
            # value = self._event_parser.update()['day'] + 1  # for test

            control_value = self._data_storage.control_value

            rate_A, rate_B = self._command_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

            if value <= control_value:
                winner = 'A'
                rate = rate_A
            else:
                winner = 'B'
                rate = rate_B

            #  pay here or write messages about that in channel, etc.

            self._broadcast_new_round_message(winner, rate)
            self._configure_new_round()

    def _configure_new_round(self):
        self._data_storage.reset_users_bets()

        now = datetime.utcnow()
        day, month, year = now.day, now.month, now.year
        tomorrow = date(year, month, day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)

        control_value = self._event_parser.update()['day']

        self._data_storage.control_value = control_value
        self._data_storage.time_limit = time_limit
        self._data_storage.update_statistics()

        self._finish = False

    def _broadcast_time_limit_message(self):
        chat_ids = self._data_storage.get_users_ids()
        timeout_message = self._data_storage.responses['40']

        rate_A, rate_B = self._command_handler.represent_rates(self._data_storage.rate_A,
                                                               self._data_storage.rate_B)

        for chat_id in chat_ids:
            self._sender.send(chat_id, timeout_message['ru'].replace('{#1}', rate_A).replace('{#2}', rate_B))

    def _broadcast_new_round_message(self, winner, rate):
        data = self._event_parser.update()
        cases_day, cases_all, date_ = data['day'], data['total'], data['date']

        message = self._data_storage.responses['41']['ru'].replace('{#1}', winner).replace('{#2}', str(rate)) \
            .replace('{#3}', str(cases_day)) \
            .replace('{#4}', str(cases_all)) \
            .replace('{#5}', str(date_))

        users = self._data_storage.get_users_ids()
        rate = float(rate)

        for user in users:
            win_amount = 0.0
            bets = self._data_storage.get_bets(user)

            for bet in bets:
                if bet['confirmed'] and bet['category'] == winner:
                    win_amount += self._data_storage.bet_amount * rate

            self._sender.send(user, message)
            self._logger.info(f'User {user} wins {win_amount}.')

            if win_amount > 0:
                self._sender.send(user, f'Ваш выигрыш составляет: {win_amount} ETH')

    def _configure_first_time(self):
        control_value = self._event_parser.update()['day']
        answer = input(f'Use {control_value} as control value? (y/n): ')

        if answer == 'y':
            self._data_storage.control_value = control_value
        else:
            control_value = int(input('enter the control value: '))
            self._data_storage.control_value = control_value

        bet_amount = self._data_storage.bet_amount
        answer = input(f'Use {bet_amount} as bet amount? (y/n): ')

        if answer == 'y':
            pass
        else:
            bet_amount = float(input('enter the bet amount: '))
            self._data_storage.bet_amount = bet_amount

        fee = float(input('enter the fee: '))
        self._data_storage.fee = fee

        now = datetime.utcnow()
        day, month, year = now.day, now.month, now.year
        tomorrow = date(year, month, day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)
        # time_limit = datetime.utcnow() + timedelta(minutes=2)  # for test

        self._data_storage.time_limit = time_limit

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

            if update and 'bet_id' in update:
                state = self._data_storage.get_state(update['chat_id'])

                if not state:
                    self._sender.send(update['chat_id'], f'Ваш голос подтвержден.\nID: {update["bet_id"]}')
                else:
                    with self._lock:
                        self._updates_queue.put(update)

                continue

            if update:
                print('start handling new update')

                if 'message' in update:
                    chat_id = update['message']['from']['id']

                    if self._data_storage.is_new_user(chat_id):
                        if 'last_name' in update['message']['from']:
                            name = f"{update['message']['from']['first_name']} {update['message']['from']['last_name']}"
                        else:
                            name = f"{update['message']['from']['first_name']}"

                        if 'username' in update['message']['from']:
                            login = update['message']['from']['username']
                        else:
                            login = None

                        self._data_storage.add_user(name, login, chat_id, 'ru')

                    if update['message']['text'].startswith('/'):
                        self._command_handler.handle_command(update, allow_bets)
                    else:
                        self._command_handler.handle_text_message(update)

                elif 'callback_query' in update:
                    chat_id = update['callback_query']['from']['id']
                    state = self._data_storage.get_state(chat_id)

                    if state:
                        self._command_handler.handle_state(chat_id, state, update, allow_bets)
                    else:
                        self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

                print('end handling new update')

    def _confirming_bets(self):
        while True:
            with self._lock:
                if self._finish:
                    return

            bets = self._data_storage.get_unconfirmed_bets()

            for bet in bets:
                chat_id = bet['chat_id']

                time.sleep(5)
                bet_id = bet['bet_id']
                self._data_storage.confirm_bet(bet_id)

                with self._lock:
                    self._updates_queue.put({'bet_id': bet_id, 'chat_id': chat_id})
