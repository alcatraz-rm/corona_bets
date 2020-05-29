import json
import logging
import math
from datetime import timedelta

from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.Sender import Sender


class UpdateHandler:
    def __init__(self, telegram_access_token: str):
        self._info_command_types = ['/start', '/help', '/how_many', '/status']
        self._action_command_types = ['/bet']
        self._admin_commands = ['/set_wallet_a', '/set_wallet_b', '/set_fee', '/set_vote_end_time']

        self._data_storage = DataStorage()
        self._logger = logging.getLogger('Engine.UpdateHandler')

        self._sender = Sender(telegram_access_token)
        self._ether_scan = EtherScan(telegram_access_token)

        self._logger.info('UpdateHandler configured.')

    def handle_text_message(self, message: dict, bets_allowed=True):
        try:
            chat_id = message['message']['from']['id']
        except KeyError:
            self._logger.error(f'Incorrect message structure: {message}')
            self._sender.send_message_to_creator(f'Incorrect message structure: {message}')
            return

        user_state = self._data_storage.get_user_state(chat_id)

        if user_state:
            self.handle_user_state(chat_id, user_state, message, bets_allowed)
            return

        self._sender.send_message(chat_id, self._data_storage.responses['default_answer_text'],
                                  reply_markup=self._data_storage.basic_keyboard)

    def handle_command(self, command: dict, bets_allowed: bool):
        try:
            chat_id = command['message']['from']['id']
        except KeyError:
            self._logger.error(f'Incorrect command structure: {command}')
            self._sender.send_message_to_creator(f'Incorrect command structure: {command}')
            return

        command_type = command['message']['text'].split()
        state = self._data_storage.get_user_state(chat_id)

        if state:
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id, self._data_storage.responses['default_answer_text']['ru'],
                                      reply_markup=self._data_storage.basic_keyboard)

        elif command_type[0] in self._info_command_types:
            if command_type[0] == '/start':
                self._handle_start_command(chat_id)

            elif command_type[0] == '/help':
                self._handle_help_command(chat_id)

            elif command_type[0] == '/how_many':
                self._handle_how_many_command(chat_id)

            elif command_type[0] == '/status':
                self._handle_status_command(chat_id)

        elif command_type[0] in self._action_command_types:
            if command_type[0] == '/bet':
                if bets_allowed:
                    self._handle_bet_command(command)
                else:
                    self._sender.send_message(chat_id, self._data_storage.responses['bet_timeout_message']['ru'])

        else:
            self._sender.send_message(chat_id, self._data_storage.responses['default_answer_command']['ru'])

    def handle_user_state(self, chat_id: int, state: str, message: dict, bets_allowed=True):
        if bets_allowed:
            if state == 'wait_choice':
                self._handle_user_choice(chat_id, message)

            elif state == 'wait_choice_after_vote':
                self._handle_user_choice_after_vote(chat_id, message)

            elif state == 'use_previous_wallet?':
                self._handle_wallet_choice(chat_id, message)

            elif state == 'wait_wallet':
                self._check_wallet(chat_id, message)
        else:
            self._sender.send_message(chat_id, self._data_storage.responses['bet_timeout_message']['ru'])

    def _cancel_bet_process(self, chat_id: int, message: str):
        self._data_storage.remove_last_bet(chat_id)

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)
        self._data_storage.set_user_state(None, chat_id)

    def _handle_wallet_choice(self, chat_id: int, message: dict):
        if 'callback_query' in message:
            use_previous_wallet = int(message['callback_query']['data'])
            self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

            if use_previous_wallet == -1:  # -1 means that user cancel bet process
                self._cancel_bet_process(chat_id, self._data_storage.responses['bet_rejected_message']['ru'])

            elif use_previous_wallet:
                self._data_storage.add_wallet_to_last_bet(chat_id, self._data_storage.get_last_wallet(chat_id))

                self._sender.send_message(chat_id, self._data_storage.responses['using_previous_wallet_message']['ru'],
                                          reply_markup=self._data_storage.basic_keyboard)

                self._data_storage.set_user_state(None, chat_id)

            else:
                self._data_storage.set_user_state('wait_wallet', chat_id)

                self._sender.send_message(chat_id, self._data_storage.responses['enter_ether_wallet_message']['ru'],
                                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                   'resize_keyboard': True}))

        elif 'message' in message:
            if 'text' in message['message']:
                if message['message']['text'] == 'Отменить':
                    self._cancel_bet_process(chat_id, self._data_storage.responses['bet_rejected_message']['ru'])
            else:
                self._logger.error(f'Incorrect message: {message}')

        else:
            self._cancel_bet_process(chat_id, self._data_storage.responses['default_answer_command']['ru'])

    def _check_wallet(self, chat_id: int, message: dict):
        try:
            wallet = message['message']['text']
        except KeyError:
            self._logger.error(f'Incorrect message: {message}')
            return

        if wallet == 'Отменить':
            self._cancel_bet_process(chat_id, self._data_storage.responses['bet_rejected_message']['ru'])

        elif self._ether_scan.wallet_is_correct(wallet):
            self._data_storage.add_wallet_to_last_bet(chat_id, wallet)
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id,
                                      self._data_storage.responses['wallet_successfully_changed_message']['ru'],
                                      reply_markup=self._data_storage.basic_keyboard)
        else:
            self._sender.send_message(chat_id, self._data_storage.responses['incorrect_wallet_message']['ru'])

    def _handle_user_choice_after_vote(self, chat_id: int, message: dict):
        if 'callback_query' in message:
            if message['callback_query']['data'] == 'next':
                callback_query_id = message['callback_query']['id']
                self._sender.answer_callback_query(chat_id, callback_query_id, None)

                wallet = self._data_storage.get_last_wallet(chat_id)

                if wallet:
                    self._sender.send_message(chat_id,
                                              self._data_storage.responses['use_previous_wallet_question']['ru']
                                              .replace('{wallet}', wallet)
                                              .replace('{bet_amount}', str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'inline_keyboard': [
                                                  [{
                                                      'text': self._data_storage.responses['yes']['ru'],
                                                      'callback_data': 1},
                                                      {
                                                          'text': self._data_storage.responses['change']['ru'],
                                                          'callback_data': 0}],
                                                  [{
                                                      'text': 'Отменить',
                                                      'callback_data': -1}]],
                                                  'resize_keyboard': True}))

                    self._data_storage.set_user_state('use_previous_wallet?', chat_id)
                else:
                    self._sender.send_message(chat_id,
                                              self._data_storage.responses['enter_ether_wallet_first_time_message'][
                                                  'ru']
                                              .replace('{bet_amount}', str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                       'resize_keyboard': True}))

                    self._data_storage.set_user_state('wait_wallet', chat_id)

            elif message['callback_query']['data'] == 'reject':
                self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

                self._cancel_bet_process(chat_id, self._data_storage.responses['bet_rejected_message']['ru'])

            elif message['callback_query']['data'] == 'qr':
                self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

                last_bet_category = self._data_storage.get_last_bet_category(chat_id)

                if last_bet_category == 'A':
                    qr_link = self._ether_scan.get_qr_link(self._data_storage.A_wallet)
                else:
                    qr_link = self._ether_scan.get_qr_link(self._data_storage.B_wallet)

                self._sender.send_photo(chat_id, qr_link,
                                        reply_markup=json.dumps({'inline_keyboard': [[{'text': 'Далее',
                                                                                       'callback_data': 'next'},
                                                                                      {'text': 'Отменить',
                                                                                       'callback_data': 'reject'}]],
                                                                 'resize_keyboard': True}))

                self._data_storage.set_user_state('wait_choice_after_vote', chat_id)

            else:
                self._cancel_bet_process(chat_id, self._data_storage.responses['default_answer_text']['ru'])

        else:
            self._cancel_bet_process(chat_id, self._data_storage.responses['default_answer_text']['ru'])

    def _handle_user_choice(self, chat_id, message):
        if 'callback_query' in message:
            category = message['callback_query']['data']
            self._data_storage.add_bet(chat_id, category)

            self._sender.answer_callback_query(chat_id, message['callback_query']['id'],
                                               self._data_storage.responses['you_voted_for_message']['ru']
                                               .replace('{category}', category))

            message_after_choice = self._data_storage.responses['message_after_vote']['ru'] \
                .replace('{category}', category) \
                .replace('{bet_amount}', str(self._data_storage.bet_amount)) \
                .replace('{time_limit}', str(self._data_storage.time_limit))

            self._sender.send_message(chat_id, message_after_choice, reply_markup=json.dumps({'hide_keyboard': True}))

            if category == 'A':
                wallet = self._data_storage.A_wallet
            else:
                wallet = self._data_storage.B_wallet

            self._sender.send_message(chat_id, wallet,
                                      reply_markup=json.dumps({'inline_keyboard': [[{'text': 'QR',
                                                                                     'callback_data': 'qr'},
                                                                                    {'text': 'Далее',
                                                                                     'callback_data': 'next'}],
                                                                                   [{'text': 'Отменить',
                                                                                     'callback_data': 'reject'}]],
                                                               'resize_keyboard': True}))

            self._data_storage.set_user_state('wait_choice_after_vote', chat_id)

        elif 'message' in message:
            if 'text' in message['message']:
                if message['message']['text'] == 'Отменить':
                    self._cancel_bet_process(chat_id, self._data_storage.responses['bet_rejected_message']['ru'])
            else:
                self._logger.error(f'Incorrect message: {message}')

        else:
            self._cancel_bet_process(chat_id, self._data_storage.responses['default_answer_text']['ru'])

    def _handle_bet_command(self, command: dict):
        try:
            chat_id = command['message']['from']['id']
        except KeyError:
            self._logger.error(f'Error while trying to extract chat_id, incorrect command: {command}')
            return

        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        announcement = self._data_storage.responses['announcement']['ru'] \
            .replace('{cases_day}', str(self._data_storage.cases_day)) \
            .replace('{control_value}', str(self._data_storage.control_value)) \
            .replace('{rate_A}', rate_A) \
            .replace('{rate_B}', rate_B) \
            .replace('{control_value + 1}', str(self._data_storage.control_value + 1)) \
            .replace('{bet_amount}', str(self._data_storage.bet_amount)) \
            .replace('{time_limit}', str(self._data_storage.time_limit))

        self._sender.send_message(chat_id, announcement, reply_markup=json.dumps({'inline_keyboard': [
            [{'text': 'A', 'callback_data': 'A'},
             {'text': 'B', 'callback_data': 'B'}]],
            'resize_keyboard': True}))

        self._sender.send_message(chat_id, self._data_storage.responses['reject_message']['ru'],
                                  reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                           'resize_keyboard': True}))

        self._data_storage.set_user_state('wait_choice', chat_id)

    @staticmethod
    def represent_rates(rate_A, rate_B) -> (str, str):
        if rate_A != 'N/a' and rate_B != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(math.trunc(rate_B * 1000) / 1000)

        elif rate_A != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(rate_B)

        elif rate_B != 'N/a':
            return str(math.trunc(rate_B * 1000) / 1000), str(rate_A)

        else:
            return str(rate_A), str(rate_B)

    def _handle_start_command(self, chat_id: int):
        self._sender.send_message(chat_id, self._data_storage.responses['start_message']['ru'],
                                  reply_markup=self._data_storage.basic_keyboard)

    def _handle_help_command(self, chat_id: int):
        message = self._data_storage.responses['help_message']['ru']
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        message = message.replace('{control_value}', str(self._data_storage.control_value)) \
            .replace('{control_value + 1}', str(self._data_storage.control_value + 1)) \
            .replace('{rate_A}', rate_A) \
            .replace('{rate_B}', rate_B) \
            .replace('{bet_amount}', str(self._data_storage.bet_amount)) \
            .replace('{time_limit}', str(self._data_storage.time_limit))

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_how_many_command(self, chat_id: int):
        message = self._data_storage.responses['how_many_message']['ru'] \
            .replace('{cases_day}', str(self._data_storage.cases_day)) \
            .replace('{cases_total}', str(self._data_storage.cases_total)) \
            .replace('{time_limit}', str(self._data_storage.date - timedelta(hours=3)))

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_status_command(self, chat_id: int):
        bet_list = self._data_storage.get_user_bets(chat_id)
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        if len(bet_list) > 0:
            status_message = ''

            for n, bet in enumerate(bet_list):
                if bet['confirmed']:
                    status = self._data_storage.responses['confirmed']['ru']

                else:
                    status = self._data_storage.responses['unconfirmed']['ru']

                if bet['category'] == 'A':
                    rate = rate_A
                else:
                    rate = rate_B

                status_message += self._data_storage.responses['status_one_bet_message']['ru'] \
                    .replace('{bet_number}', str(n + 1)) \
                    .replace('{category}', bet['category']) \
                    .replace('{rate}', str(rate)).replace('{wallet}', bet['wallet']).replace('{status}', status)

            self._sender.send_message(chat_id, status_message,
                                      reply_markup=json.dumps({'keyboard': [
                                          [{'text': '/bet'}, {'text': '/help'}]],
                                          'resize_keyboard': True}))
        else:
            self._sender.send_message(chat_id, self._data_storage.responses['no_active_bets_message']['ru'])
