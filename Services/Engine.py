import json
import logging
import math
import os
import platform
import threading
import time
from copy import deepcopy
from datetime import datetime, date, timedelta
from queue import Queue

import requests

from Services.CommandHandler import CommandHandler
from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.EventParser import EventParser
from Services.Sender import Sender


class Engine:
    def __init__(self, telegram_access_token):
        self._logger = logging.getLogger('Engine')
        self._configure_logger()

        self._telegram_access_token = telegram_access_token
        self._requests_url = f'https://api.telegram.org/bot{telegram_access_token}/'

        self._command_handler = CommandHandler(self._telegram_access_token)
        self._event_parser = EventParser()
        self._ether_scan = EtherScan()
        self._sender = Sender(self._telegram_access_token)

        self._data_storage = DataStorage()
        self._data_storage.update_statistics()

        self._updates_queue = Queue()
        self._lock = threading.Lock()
        self._threads_end_flag = False

        self._logger.info('Engine initialized.')

    def _configure_logger(self):
        self._logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler('log.log', 'w', 'utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(file_handler)

        self._logger.info(f'Platform: {platform.system().lower()}')
        self._logger.info(f'WD: {os.getcwd()}')

    def _get_updates(self, offset=None, timeout=30):
        return requests.get(self._requests_url + 'getUpdates', {'timeout': timeout, 'offset': offset}).json()['result']

    def _log_new_message(self, message):
        log_message = {'type': 'message'}

        chat_id = message['message']['from']['id']
        log_message['from'] = {'chat_id': chat_id}

        if 'last_name' in message['message']['from']:
            name = f"{message['message']['from']['first_name']} {message['message']['from']['last_name']}"
        else:
            name = f"{message['message']['from']['first_name']}"

        log_message['from']['name'] = name

        if 'username' in message['message']['from']:
            log_message['from']['username'] = message['message']['from']['username']

        log_message['text'] = message['message']['text']
        log_message['update_id'] = message['update_id']

        self._logger.info(f'Get new update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def _log_callback_query(self, callback_query):
        log_message = {'type': 'callback_query', 'from': {'chat_id': callback_query['callback_query']['from']['id']}}

        if 'last_name' in callback_query['callback_query']['from']:
            name = f"{callback_query['callback_query']['from']['first_name']} " \
                   f"{callback_query['callback_query']['from']['last_name']}"
        else:
            name = f"{callback_query['callback_query']['from']['first_name']}"

        log_message['from']['name'] = name

        if 'username' in callback_query['callback_query']['from']:
            log_message['from']['username'] = callback_query['callback_query']['from']['username']

        log_message['update_id'] = callback_query['update_id']
        log_message['callback_query_id'] = callback_query['callback_query']['id']
        log_message['data'] = callback_query['callback_query']['data']

        self._logger.info(f'Get new update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def _log_telegram_update(self, update):
        if 'message' in update:
            self._log_new_message(update)
        elif 'callback_query' in update:
            self._log_callback_query(update)
        else:
            self._logger.warning(f'Get new update (unknown type): {json.dumps(update, indent=4, ensure_ascii=False)}')

    def _wait(self):
        while True:
            remaining_time = (self._data_storage.time_limit - datetime.utcnow()).total_seconds()

            if remaining_time <= 5:
                with self._lock:
                    self._threads_end_flag = True
                return

            if remaining_time // 2 > 3:
                time.sleep(remaining_time // 2)
            else:
                time.sleep(3)

    def start_loop(self):
        self._configure_first_time()

        while True:
            listening_thread = threading.Thread(target=self._listening_for_updates, daemon=True)
            handling_thread = threading.Thread(target=self._updates_handling, daemon=True)
            confirm_bets_thread = threading.Thread(target=self._bets_confirming, daemon=True)

            listening_thread.start()
            handling_thread.start()
            confirm_bets_thread.start()

            self._logger.debug('Start listening, handling and bets verifying threads.')
            self._logger.debug(f'Time limit: {self._data_storage.time_limit}')

            self._wait()

            listening_thread.join()
            handling_thread.join()

            self._logger.debug('Listening, handling and bets verifying threads joined.')

            self._broadcast_time_limit_message()

            self._threads_end_flag = False

            listening_thread.start()
            handling_thread.start()

            self._logger.debug('Start listening and handling threads (bets are not allowed).')

            last_update_time = self._event_parser.update()['date']

            while True:
                date_ = self._event_parser.update()['date']

                if date_ != last_update_time:
                    self._threads_end_flag = True
                    break

                time.sleep(300)

            listening_thread.join()
            handling_thread.join()

            self._logger.debug('listening and handling threads (bets are not allowed) joined')

            new_control_value = self._data_storage.cases_day
            self._data_storage.update_statistics()

            rate_A, rate_B = self._command_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

            if self._data_storage.cases_day <= self._data_storage.control_value:
                winner = 'A'
                rate = rate_A
            else:
                winner = 'B'
                rate = rate_B

            self._broadcast_new_round_message(winner, rate)
            self._configure_new_round(new_control_value)

    def _configure_new_round(self, new_control_value):
        self._data_storage.reset_bets()

        now = datetime.utcnow()
        tomorrow = date(now.year, now.month, now.day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        self._data_storage.time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)
        self._data_storage.control_value = new_control_value

        self._threads_end_flag = False

    def _broadcast_time_limit_message(self):
        users_ids_list = self._data_storage.get_users_ids_list()
        rate_A, rate_B = self._command_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        timeout_message = self._data_storage.responses['40']['ru'].replace('{#1}', rate_A).replace('{#2}', rate_B)

        for user_id in users_ids_list:
            self._sender.send_message(user_id, timeout_message)

    def _broadcast_new_round_message(self, winner, rate):
        new_round_message = self._data_storage.responses['41']['ru'].replace('{#1}', winner).replace('{#2}', str(rate)) \
            .replace('{#3}', str(self._data_storage.cases_day)) \
            .replace('{#4}', str(self._data_storage.cases_total)) \
            .replace('{#5}', str(self._data_storage.date))

        users = self._data_storage.get_users_ids_list()
        rate = float(rate)

        for user in users:
            win_amount = 0.0
            bet_list = self._data_storage.get_user_bets(user)

            for bet in bet_list:
                if bet['confirmed'] and bet['category'] == winner:
                    win_amount += self._data_storage.bet_amount * rate

            self._sender.send_message(user, new_round_message)
            self._logger.info(f'User {user} wins {win_amount}.')

            if win_amount > 0:
                self._sender.send_message(user,
                                          f'Ваш выигрыш составляет: {str(math.trunc(win_amount * 1000) / 1000)} ETH')

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
        tomorrow = date(now.year, now.month, now.day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        self._data_storage.time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)

        self._threads_end_flag = False

        self._logger.info('First configuration completed.')

    def _listening_for_updates(self):
        offset = None

        while True:
            with self._lock:
                if self._threads_end_flag:
                    break

            updates_list = self._get_updates(offset)

            for update in updates_list:
                self._log_telegram_update(update)

                with self._lock:
                    self._updates_queue.put(update)

                offset = update['update_id'] + 1

    @staticmethod
    def _extract_user_data_from_message(update):
        if 'last_name' in update['message']['from']:
            name = f"{update['message']['from']['first_name']} {update['message']['from']['last_name']}"
        else:
            name = f"{update['message']['from']['first_name']}"

        if 'username' in update['message']['from']:
            login = update['message']['from']['username']
        else:
            login = None

        return name, login

    def _handle_message(self, message, bets_allowed):
        chat_id = message['message']['from']['id']

        if self._data_storage.is_new_user(chat_id):
            name, login = self._extract_user_data_from_message(message)
            self._data_storage.add_user(name, login, chat_id, 'ru')

        if message['message']['text'].startswith('/'):
            self._command_handler.handle_command(message, bets_allowed)
        else:
            self._command_handler.handle_text_message(message)

    def _handle_bet_verifying_update(self, update):
        state = self._data_storage.get_user_state(update['chat_id'])

        if state:
            with self._lock:
                self._updates_queue.put(update)
        else:
            self._sender.send_message(update['chat_id'], f'Ваш голос подтвержден.\nID: {update["bet_id"]}')

    def _handle_callback_query(self, update, bets_allowed):
        chat_id = update['callback_query']['from']['id']
        state = self._data_storage.get_user_state(chat_id)

        if state:
            self._command_handler.handle_user_state(chat_id, state, update, bets_allowed)
        else:
            self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

    def _updates_handling(self, bets_allowed=True):
        while True:
            with self._lock:
                if self._threads_end_flag:
                    break

            with self._lock:
                if not self._updates_queue.empty():
                    update = self._updates_queue.get()
                else:
                    continue

            if update:
                if 'message' in update:
                    self._handle_message(update, bets_allowed)

                elif 'callback_query' in update:
                    self._handle_callback_query(update, bets_allowed)

                elif 'bet_id' in update:
                    self._handle_bet_verifying_update(update)

    def _bets_confirming(self):
        while True:
            with self._lock:
                if self._threads_end_flag:
                    return

            bets_list = self._data_storage.get_unconfirmed_bets_list()

            for bet in bets_list:
                time.sleep(5)  # simulates bet verifying process
                self._data_storage.confirm_bet(bet['bet_id'])

                with self._lock:
                    self._updates_queue.put(deepcopy(bet))
