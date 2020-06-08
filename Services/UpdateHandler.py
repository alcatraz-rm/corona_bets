import json
import logging
from datetime import timedelta

from jinja2 import FileSystemLoader, Environment

from Services.Admin import Admin
from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.Sender import Sender


class UpdateHandler:
    def __init__(self, settings):
        self._info_command_types = ['/start', '/help', '/how_many', '/status']
        self._action_command_types = ['/bet']
        self._admin_commands = ['/set_wallet', '/set_fee', '/set_vote_end_time', '/admin_cancel',
                                '/stat', '/pay_out']

        self._data_storage = DataStorage(settings)
        self._templates_env = Environment(loader=FileSystemLoader('user_responses'))
        self._logger = logging.getLogger('Engine.UpdateHandler')

        self._sender = Sender(settings)
        self._ether_scan = EtherScan(settings)
        self._admin = Admin(settings)

        self._logger.info('UpdateHandler configured.')

    def handle_text_message(self, message: dict, bets_allowed=True):
        if self._admin.is_authorize_query(message):
            self._admin.auth(message)
            return

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

        self._sender.send_message(chat_id, self._templates_env.get_template('default_answer_text.jinja').render(),
                                  reply_markup=self._data_storage.basic_keyboard)

    def handle_command(self, command: dict, bets_allowed: bool):
        try:
            chat_id = command['message']['from']['id']
        except KeyError:
            self._logger.error(f'Incorrect command structure: {command}')
            self._sender.send_message_to_creator(f'Incorrect command structure: {command}')
            return

        command_type = command['message']['text'].split()

        if command_type[0] in self._admin_commands:
            self._admin.handle_command(command)
            return

        state = self._data_storage.get_user_state(chat_id)

        if state:
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id, self._templates_env.get_template('default_answer_text.jinja').render(),
                                      reply_markup=self._data_storage.basic_keyboard)

        if command_type[0] in self._info_command_types:
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
                    self._sender.send_message(chat_id,
                                              self._templates_env.get_template('bet_timeout_message.jinja').render())

        else:
            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('default_answer_command.jinja').render())

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
            self._sender.send_message(chat_id, self._templates_env.get_template('bet_timeout_message.jinja.jinja'))

    def _cancel_bet_process(self, chat_id: int, message: str):
        self._data_storage.remove_last_bet(chat_id)

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)
        self._data_storage.set_user_state(None, chat_id)

    def _handle_wallet_choice(self, chat_id: int, message: dict):
        if 'callback_query' in message:
            use_previous_wallet = int(message['callback_query']['data'])
            self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

            if use_previous_wallet == -1:  # -1 means that user cancel bet process
                self._cancel_bet_process(chat_id,
                                         self._templates_env.get_template('bet_rejected_message.jinja').render())

            elif use_previous_wallet:
                self._data_storage.add_wallet_to_last_bet(chat_id, self._data_storage.get_last_wallet(chat_id))

                self._sender.send_message(chat_id,
                                          self._templates_env.get_template('using_previous_wallet_message.jinja')
                                          .render(),
                                          reply_markup=self._data_storage.basic_keyboard)

                self._data_storage.set_user_state(None, chat_id)

            else:
                self._data_storage.set_user_state('wait_wallet', chat_id)

                self._sender.send_message(chat_id,
                                          self._templates_env.get_template('enter_ether_wallet_message.jinja').render(),
                                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                   'resize_keyboard': True}))

        elif 'message' in message:
            if 'text' in message['message']:
                if message['message']['text'] == 'Отменить':
                    self._cancel_bet_process(chat_id,
                                             self._templates_env.get_template('bet_rejected_message.jinja').render())

            else:
                self._logger.error(f'Incorrect message: {message}')

        else:
            self._cancel_bet_process(chat_id, self._templates_env.get_template('default_answer_command.jinja').render())

    def _check_wallet(self, chat_id: int, message: dict):
        try:
            wallet = message['message']['text']
        except KeyError:
            self._logger.error(f'Incorrect message: {message}')
            return

        if wallet == 'Отменить':
            self._cancel_bet_process(chat_id, self._templates_env.get_template('bet_rejected_message.jinja').render())

        elif self._ether_scan.wallet_is_correct(wallet):
            self._data_storage.add_wallet_to_last_bet(chat_id, wallet)
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('wallet_successfully_changed_message.jinja')
                                      .render(),
                                      reply_markup=self._data_storage.basic_keyboard)
        else:
            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('incorrect_wallet_message.jinja').render())

    def _handle_user_choice_after_vote(self, chat_id: int, message: dict):
        if 'callback_query' in message:
            if message['callback_query']['data'] == 'next':
                callback_query_id = message['callback_query']['id']
                self._sender.answer_callback_query(chat_id, callback_query_id, '')

                wallet = self._data_storage.get_last_wallet(chat_id)

                if wallet:
                    self._sender.send_message(chat_id,
                                              self._templates_env.get_template(
                                                  'use_previous_wallet_question.jinja').render(wallet=wallet)
                                              .replace('{wallet}', wallet)
                                              .replace('{bet_amount}', str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'inline_keyboard': [
                                                  [{
                                                      'text': self._templates_env.get_template('yes.jinja').render(),
                                                      'callback_data': 1},
                                                      {
                                                          'text': self._templates_env.get_template(
                                                              'change.jinja').render(),
                                                          'callback_data': 0}],
                                                  [{
                                                      'text': 'Отменить',
                                                      'callback_data': -1}]],
                                                  'resize_keyboard': True}))

                    self._data_storage.set_user_state('use_previous_wallet?', chat_id)
                else:
                    self._sender.send_message(chat_id,
                                              self._templates_env.get_template(
                                                  'enter_ether_wallet_first_time_message.jinja').render(
                                                  bet_amoun=str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                       'resize_keyboard': True}))

                    self._data_storage.set_user_state('wait_wallet', chat_id)

            elif message['callback_query']['data'] == 'reject':
                self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

                self._cancel_bet_process(chat_id,
                                         self._templates_env.get_template('bet_rejected_message.jinja').render())

            elif message['callback_query']['data'] == 'qr':
                self._sender.answer_callback_query(chat_id, message['callback_query']['id'], '')

                last_bet_category = self._data_storage.get_last_bet_category(chat_id)

                if last_bet_category == 'A':
                    if self._data_storage.A_wallet_qr_id:
                        qr = self._data_storage.A_wallet_qr_id
                    else:
                        qr = self._ether_scan.get_qr_link(self._data_storage.A_wallet)
                else:
                    if self._data_storage.B_wallet_qr_id:
                        qr = self._data_storage.B_wallet_qr_id
                    else:
                        qr = self._ether_scan.get_qr_link(self._data_storage.B_wallet)

                file_id = self._sender.send_photo(chat_id, qr,
                                                  reply_markup=json.dumps({'inline_keyboard': [
                                                      [{'text': 'Далее',
                                                        'callback_data': 'next'},
                                                       {'text': 'Отменить',
                                                        'callback_data': 'reject'}]],
                                                      'resize_keyboard': True}))

                if last_bet_category == 'A' and file_id:
                    self._data_storage.A_wallet_qr_id = file_id
                elif file_id:
                    self._data_storage.B_wallet_qr_id = file_id

                self._data_storage.set_user_state('wait_choice_after_vote', chat_id)

            else:
                self._cancel_bet_process(chat_id,
                                         self._templates_env.get_template('default_answer_text.jinja').render())

        else:
            self._cancel_bet_process(chat_id,
                                     self._templates_env.get_template('default_answer_text.jinja').render())

    def _handle_user_choice(self, chat_id, message):
        if 'callback_query' in message:
            category = message['callback_query']['data']
            self._data_storage.add_bet(chat_id, category)

            self._sender.answer_callback_query(chat_id, message['callback_query']['id'],
                                               self._templates_env.get_template('you_voted_for_message.jinja').render(
                                                   category=category))

            message_after_choice = self._templates_env.get_template('message_after_vote.jinja').render(
                category=category,
                bet_amount=str(self._data_storage.bet_amount),
                time_limit=str(self._data_storage.time_limit))

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
                    self._cancel_bet_process(chat_id,
                                             self._templates_env.get_template('bet_rejected_message.jinja').render())
            else:
                self._logger.error(f'Incorrect message: {message}')

        else:
            self._cancel_bet_process(chat_id,
                                     self._templates_env.get_template('default_answer_text.jinja').render())

    def _handle_bet_command(self, command: dict):
        try:
            chat_id = command['message']['from']['id']
        except KeyError:
            self._logger.error(f'Error while trying to extract chat_id, incorrect command: {command}')
            return

        rate_A, rate_B = self._data_storage.represented_rates

        announcement = self._templates_env.get_template('announcement.jinja').render(
            cases_day=str(self._data_storage.cases_day),
            control_value=str(self._data_storage.control_value),
            rate_A=rate_A,
            rate_B=rate_B,
            control_value_plus_1=str(self._data_storage.control_value + 1),
            bet_amount=str(self._data_storage.bet_amount),
            time_limit=str(self._data_storage.time_limit))

        self._sender.send_message(chat_id, announcement, reply_markup=json.dumps({'inline_keyboard': [
            [{'text': 'A', 'callback_data': 'A'},
             {'text': 'B', 'callback_data': 'B'}]],
            'resize_keyboard': True}))

        self._sender.send_message(chat_id, self._templates_env.get_template('reject_message.jinja').render(),
                                  reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                           'resize_keyboard': True}))

        self._data_storage.set_user_state('wait_choice', chat_id)

    def _handle_start_command(self, chat_id: int):
        self._sender.send_message(chat_id, self._templates_env.get_template('start_message.jinja').render(),
                                  reply_markup=self._data_storage.basic_keyboard)

    def _handle_help_command(self, chat_id: int):
        rate_A, rate_B = self._data_storage.represented_rates

        message = self._templates_env.get_template('help_message.jinja').render(
            control_value_plus_1=str(self._data_storage.control_value + 1),
            control_value=str(self._data_storage.control_value),
            rate_A=rate_A,
            rate_B=rate_B,
            bet_amount=str(self._data_storage.bet_amount),
            time_limit=str(self._data_storage.time_limit)
        )

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_how_many_command(self, chat_id: int):
        message = self._templates_env.get_template('how_many_message.jinja').render(
            cases_day=str(self._data_storage.cases_day),
            cases_total=str(self._data_storage.cases_total),
            time_limit=str(self._data_storage.date - timedelta(hours=3))
        )

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_status_command(self, chat_id: int):
        bet_list = self._data_storage.get_user_bets(chat_id)
        rate_A, rate_B = self._data_storage.represented_rates

        if len(bet_list) > 0:
            status_message = ''

            for n, bet in enumerate(bet_list):
                if bet['confirmed']:
                    status = self._templates_env.get_template('confirmed.jinja').render()

                else:
                    status = self._templates_env.get_template('unconfirmed.jinja').render()

                if bet['category'] == 'A':
                    rate = rate_A
                else:
                    rate = rate_B

                status_message += self._templates_env.get_template('status_one_bet_message.jinja').render(
                    bet_number=str(n + 1),
                    category=bet['category'],
                    rate=str(rate),
                    wallet=bet['wallet'],
                    status=status
                )

            self._sender.send_message(chat_id, status_message,
                                      reply_markup=json.dumps({'keyboard': [
                                          [{'text': '/bet'}, {'text': '/help'}]],
                                          'resize_keyboard': True}))
        else:
            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('no_active_bets_message.jinja').render())
