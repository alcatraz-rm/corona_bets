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
from jinja2 import FileSystemLoader, Environment

from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.RequestManager import RequestManager
from Services.Sender import Sender
from Services.StatisticsParser import StatisticsParser
from Services.UpdateHandler import UpdateHandler


class Engine:
    def __init__(self, telegram_access_token: str, etherscan_api_token: str):
        self._logger = logging.getLogger('Engine')
        self._configure_logger()

        self._requests_url = f'https://api.telegram.org/bot{telegram_access_token}/'

        self._update_handler = UpdateHandler(telegram_access_token, etherscan_api_token)
        self._statistics_parser = StatisticsParser()
        self._ether_scan = EtherScan(telegram_access_token, etherscan_api_token)
        self._sender = Sender(telegram_access_token)
        self._request_manager = RequestManager()
        self._templates_env = Environment(loader=FileSystemLoader('user_responses'))

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

        self._logger.info('Logger configured.')

    def _get_updates(self, offset=None, timeout=30) -> list:
        response = self._request_manager.request(self._requests_url + 'getUpdates',
                                                 {'timeout': timeout, 'offset': offset}, method='get')

        if isinstance(response, requests.Response):
            updates = response.json()
        else:
            self._logger.error(f'Error occurred in get_updates: {response}')
            self._sender.send_message_to_creator(f'Error occurred in get_updates: {response}')
            return []

        if 'result' in updates:
            return updates['result']
        else:
            self._logger.error(f'Not result-key in updates: {updates}')
            self._sender.send_message_to_creator(f'Not result-key in updates: {updates}')
            return []

    def _log_new_message(self, message: dict):
        log_message = {'type': 'message'}

        try:
            chat_id = message['message']['from']['id']

        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Message that an error occurred during processing: {message}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Message that an error occurred during processing: {message}')
            return

        log_message['from'] = {'chat_id': chat_id}

        try:
            if 'last_name' in message['message']['from']:
                name = f"{message['message']['from']['first_name']} {message['message']['from']['last_name']}"
            else:
                name = f"{message['message']['from']['first_name']}"
        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Message that an error occurred during processing: {message}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Message that an error occurred during processing: {message}')
            return

        log_message['from']['name'] = name

        try:
            if 'username' in message['message']['from']:
                log_message['from']['username'] = message['message']['from']['username']

            log_message['text'] = message['message']['text']
            log_message['update_id'] = message['update_id']

        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Message that an error occurred during processing: {message}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Message that an error occurred during processing: {message}')
            return

        self._logger.info(f'Get new update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def _log_callback_query(self, callback_query: dict):
        try:
            log_message = {'type': 'callback_query',
                           'from': {'chat_id': callback_query['callback_query']['from']['id']}}
        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Callback query that an error occurred during processing: {callback_query}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Callback query that an error occurred during processing: {callback_query}')
            return

        try:
            if 'last_name' in callback_query['callback_query']['from']:
                name = f"{callback_query['callback_query']['from']['first_name']} " \
                       f"{callback_query['callback_query']['from']['last_name']}"
            else:
                name = f"{callback_query['callback_query']['from']['first_name']}"
        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Callback query that an error occurred during processing: {callback_query}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Callback query that an error occurred during processing: {callback_query}')
            return

        log_message['from']['name'] = name

        if 'username' in callback_query['callback_query']['from']:
            log_message['from']['username'] = callback_query['callback_query']['from']['username']

        try:
            log_message['update_id'] = callback_query['update_id']
            log_message['callback_query_id'] = callback_query['callback_query']['id']
            log_message['data'] = callback_query['callback_query']['data']
        except KeyError as exception:
            self._logger.error(f'Logging error: {exception}\n'
                               f'Callback query that an error occurred during processing: {callback_query}')
            self._sender.send_message_to_creator(f'Logging error: {exception}\n'
                                                 f'Callback query that an error occurred during processing: {callback_query}')
            return

        self._logger.info(f'Get new update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def _log_telegram_update(self, update: dict):
        if 'message' in update:
            self._log_new_message(update)
        elif 'callback_query' in update:
            self._log_callback_query(update)
        else:
            self._logger.warning(f'Get new update (unknown type): {json.dumps(update, indent=4, ensure_ascii=False)}')
            self._sender.send_message_to_creator(
                f'Get new update (unknown type): {json.dumps(update, indent=4, ensure_ascii=False)}')

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

            self._logger.debug('Listening, handling and bets verifying threads joined (bets are allowed).')

            self._broadcast_time_limit_message()

            self._threads_end_flag = False

            listening_thread = threading.Thread(target=self._listening_for_updates, daemon=True)
            handling_thread = threading.Thread(target=self._updates_handling, daemon=True, args=(False,))

            listening_thread.start()
            handling_thread.start()

            self._logger.debug('Start listening and handling threads (bets are not allowed).')

            last_update_time = self._statistics_parser.update()['date']

            while True:
                date_ = self._statistics_parser.update()['date']

                if date_ != last_update_time:
                    self._threads_end_flag = True
                    break

                time.sleep(300)

            listening_thread.join()
            handling_thread.join()

            self._logger.debug('listening and handling threads (bets are not allowed) joined.')

            new_control_value = self._data_storage.cases_day
            self._data_storage.update_statistics()

            rate_A, rate_B = self._update_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

            if self._data_storage.cases_day <= self._data_storage.control_value:
                winner = 'A'
                rate = rate_A
            else:
                winner = 'B'
                rate = rate_B

            self._broadcast_new_round_message(winner, rate)
            self._configure_new_round(new_control_value)

    def _configure_new_round(self, new_control_value: int):
        self._data_storage.reset_bets()

        now = datetime.utcnow()
        tomorrow = date(now.year, now.month, now.day) + timedelta(days=1)

        # time limit - 6:00 GMT (9:00 MSK)
        self._data_storage.time_limit = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 0, 0, 0)
        self._data_storage.control_value = new_control_value

        self._threads_end_flag = False

    def _broadcast_time_limit_message(self):
        users_ids_list = self._data_storage.get_users_ids_list()
        rate_A, rate_B = self._update_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        timeout_message = self._templates_env.get_template('timeout_message.jinja').render(rate_A=rate_A, rate_B=rate_B)

        for user_id in users_ids_list:
            self._sender.send_message(user_id, timeout_message)

    def _broadcast_new_round_message(self, winner: str, rate: float):
        new_round_message = self._templates_env \
            .get_template('new_round_message.jinja') \
            .render(rate=str(rate), winner=winner, cases_day=str(self._data_storage.cases_day),
                    cases_total=str(self._data_storage.cases_total), last_update_time=str(self._data_storage.date))

        users = self._data_storage.get_users_ids_list()
        rate = float(rate)

        for user in users:
            self._sender.send_message(user, new_round_message)

            bet_list = self._data_storage.get_user_bets(user)
            win_message = self._generate_win_message(bet_list, winner, rate)

            if win_message:
                self._sender.send_message(user, win_message)

    # TODO: optimize this (you may not form all message, before you should try ro find one verified bet
    #  with required category
    # TODO: optimize it with Jinja
    def _generate_win_message(self, bet_list: list, winner: str, rate: float):
        total_amount = 0.0
        message = ''

        for n, bet in enumerate(bet_list):
            if bet['confirmed'] and bet['category'] == winner:
                current_amount = self._data_storage.bet_amount * rate

                message += self._templates_env.get_template('win_message_one_bet.jinja') \
                    .render(bet_number=str(n),
                            wallet=bet['wallet'],
                            amount=str(math.trunc(current_amount * 1000) / 1000))

                total_amount += current_amount

        if total_amount > 0:
            return message + self._templates_env.get_template('win_message_total_amount.jinja') \
                .render(
                amount=str(math.trunc(total_amount * 1000) / 1000))

    def _configure_first_time(self):
        control_value = self._statistics_parser.update()['day']
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

    def _extract_user_data_from_message(self, update: dict) -> (str, str):
        defaults = 'Unknown', 'Unknown'

        try:
            if 'last_name' in update['message']['from']:
                name = f"{update['message']['from']['first_name']} {update['message']['from']['last_name']}"
            else:
                name = f"{update['message']['from']['first_name']}"
        except KeyError as exception:
            self._logger.error(f'Error occurred while trying to extract user data from update: {exception}\n'
                               f'Update: {update}')
            self._sender.send_message_to_creator(
                f'Error occurred while trying to extract user data from update: {exception}\n'
                f'Update: {update}')

            return defaults

        try:
            if 'username' in update['message']['from']:
                login = update['message']['from']['username']
            else:
                login = None
        except KeyError as exception:
            self._logger.error(f'Error occurred while trying to extract user data from update: {exception}\n'
                               f'Update: {update}')
            self._sender.send_message_to_creator(
                f'Error occurred while trying to extract user data from update: {exception}\n'
                f'Update: {update}')

            return defaults

        return name, login

    def _handle_message(self, message: dict, bets_allowed: bool):
        if 'message' in message and 'text' in message['message']:
            chat_id = message['message']['from']['id']

            if self._data_storage.is_new_user(chat_id):
                name, login = self._extract_user_data_from_message(message)
                self._data_storage.add_user(name, login, chat_id, 'ru')

            if message['message']['text'].startswith('/'):
                self._update_handler.handle_command(message, bets_allowed)
            else:
                self._update_handler.handle_text_message(message)
        else:
            self._logger.error(f'Invalid message structure: {message}')
            self._sender.send_message_to_creator(f'Invalid message structure: {message}')

    def _handle_bet_verifying_update(self, update: dict):
        user_state = self._data_storage.get_user_state(update['chat_id'])
        bets_list = self._data_storage.get_user_bets(update['chat_id'])

        rate_A, rate_B = self._update_handler.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        if update['category'] == 'A':
            rate = rate_A
        else:
            rate = rate_B

        for n, bet in enumerate(bets_list):
            if bet['bet_id'] == update['bet_id']:
                bet_number = n + 1
                break

        if user_state:
            with self._lock:
                self._updates_queue.put(update)
        else:
            self._sender.send_message(update['chat_id'],
                                      self._templates_env.get_template('bet_confirmed_message.jinja').render(
                                          bet_number=str(bet_number),
                                          category=update['category'],
                                          rate=rate, wallet=update['wallet']))

    def _handle_callback_query(self, update: dict, bets_allowed: bool):
        try:
            chat_id = update['callback_query']['from']['id']
            state = self._data_storage.get_user_state(chat_id)

            if state:
                self._update_handler.handle_user_state(chat_id, state, update, bets_allowed)
            else:
                self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

        except KeyError:
            self._logger.error(f'Invalid callback_query structure: {update}')
            self._sender.send_message_to_creator(f'Invalid callback_query structure: {update}')

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

                else:
                    self._logger.warning(f'Get invalid update: {update}')

    def _bets_confirming(self):
        while True:
            with self._lock:
                if self._threads_end_flag:
                    return

            bets_list = self._data_storage.get_unconfirmed_bets_all()

            for bet in bets_list:
                time.sleep(5)  # simulates bet verifying process
                self._data_storage.confirm_bet(bet['bet_id'], 0)

                with self._lock:
                    self._updates_queue.put(deepcopy(bet))

    def _bets_confirming_true(self):
        while True:
            with self._lock:
                if self._threads_end_flag:
                    return

            users_list = self._data_storage.get_users_with_unconfirmed_bets()

            if not users_list:
                time.sleep(10)
                continue

            for user in users_list:
                confirmed_bets = self._ether_scan.confirm_bets(user)

                for bet in confirmed_bets:
                    with self._lock:
                        self._updates_queue.put(deepcopy(bet))
