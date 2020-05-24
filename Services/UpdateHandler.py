import json
from datetime import timedelta
import math

from Services.Sender import Sender
from Services.EtherScan import EtherScan
from Services.DataStorage import DataStorage


class UpdateHandler:
    def __init__(self, telegram_access_token):
        self._info_command_types = ['/start', '/help', '/how_many', '/status']
        self._action_command_types = ['/bet']
        self._admin_commands = ['/set_wallet_a', '/set_wallet_b', '/set_fee', '/set_vote_end_time']

        self._data_storage = DataStorage()

        self._sender = Sender(telegram_access_token)
        self._ether_scan = EtherScan()

    def handle_text_message(self, message, bets_allowed=True):
        chat_id = message['message']['from']['id']
        user_state = self._data_storage.get_user_state(chat_id)

        if user_state:
            self.handle_user_state(chat_id, user_state, message, bets_allowed)
            return

        self._sender.send_message(chat_id, 'Не понимаю, что нужно сделать, '
                                           'но могу действовать в соответствии со своими командами',
                                           reply_markup=self._data_storage.basic_keyboard)

    def handle_command(self, command, bets_allowed):
        chat_id = command['message']['from']['id']
        command_type = command['message']['text'].split()

        state = self._data_storage.get_user_state(chat_id)

        if state:
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id, 'Не понимаю, что нужно сделать, '
                                               'но могу действовать в соответствии со своими командами',
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
                    self._sender.send_message(chat_id, 'Извините, время для участия в текущей игре вышло.')

        else:
            self._sender.send_message(chat_id, self._data_storage.responses['3']['ru'])

    def handle_user_state(self, chat_id, state, message, bets_allowed=True):
        if bets_allowed:
            if state == 'wait_choice':
                self._handle_user_choice(chat_id, message)

            elif state == 'wait_choice_after_qr':
                self._handle_user_choice_after_qr(chat_id, message)

            elif state == 'use_previous_wallet?':
                self._handle_wallet_choice(chat_id, message)

            elif state == 'wait_wallet':
                self._check_wallet(chat_id, message)
        else:
            self._sender.send_message(chat_id, 'Извините, время для участия в текущей игре вышло.')

    def _cancel_bet_process(self, chat_id, message):
        self._data_storage.remove_last_bet(chat_id)

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)
        self._data_storage.set_user_state(None, chat_id)

    def _handle_wallet_choice(self, chat_id, message):
        if 'callback_query' in message:
            use_previous_wallet = int(message['callback_query']['data'])
            self._sender.answer_callback_query(chat_id, message['callback_query']['id'], None)

            if use_previous_wallet == -1:  # -1 means that user cancel bet process
                self._cancel_bet_process(chat_id, 'Действие отменено.')

            elif use_previous_wallet:
                self._data_storage.add_wallet_to_last_bet(chat_id, self._data_storage.get_last_wallet(chat_id))

                self._sender.send_message(chat_id, self._data_storage.responses['10']['ru'],
                                          reply_markup=self._data_storage.basic_keyboard)

                self._data_storage.set_user_state(None, chat_id)

            else:
                self._data_storage.set_user_state('wait_wallet', chat_id)
                message = self._data_storage.responses['11']['ru']

                self._sender.send_message(chat_id, message,
                                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                   'resize_keyboard': True}))

        elif 'message' in message and message['message']['text'] == 'Отменить':
            self._cancel_bet_process(chat_id, 'Действие отменено.')

        else:
            self._cancel_bet_process(chat_id, 'Я, к сожалению, умею выполнять только команды ниже :)\nСписок доступных '
                                              'команд можно узнать по команде /help.')

    def _check_wallet(self, chat_id, message):
        wallet = message['message']['text']

        if wallet == 'Отменить':
            self._cancel_bet_process(chat_id, 'Действие отменено.')

        elif self._ether_scan.wallet_is_correct(wallet):
            self._data_storage.add_wallet_to_last_bet(chat_id, wallet)
            self._data_storage.set_user_state(None, chat_id)

            self._sender.send_message(chat_id, self._data_storage.responses['12']['ru'],
                                      reply_markup=self._data_storage.basic_keyboard)
        else:
            self._sender.send_message(chat_id, self._data_storage.responses['22']['ru'])

    def _handle_user_choice_after_qr(self, chat_id, message):
        if 'callback_query' in message:
            if message['callback_query']['data'] == 'next':
                callback_query_id = message['callback_query']['id']
                self._sender.answer_callback_query(chat_id, callback_query_id, None)

                wallet = self._data_storage.get_last_wallet(chat_id)

                if wallet:
                    self._sender.send_message(chat_id,
                                              self._data_storage.responses['20']['ru'].replace('{#1}', wallet)
                                              .replace('{#2}', str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'inline_keyboard': [
                                                  [{
                                                      'text': self._data_storage.responses['8']['ru'],
                                                      'callback_data': 1},
                                                   {
                                                       'text': self._data_storage.responses['9']['ru'],
                                                       'callback_data': 0}],
                                                  [{
                                                      'text': 'Отменить',
                                                      'callback_data': -1}]],
                                                                        'resize_keyboard': True}))

                    self._data_storage.set_user_state('use_previous_wallet?', chat_id)
                else:
                    self._sender.send_message(chat_id,
                                              self._data_storage.responses['7']['ru']
                                              .replace('{#1}', str(self._data_storage.bet_amount)),
                                              reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                       'resize_keyboard': True}))

                    self._data_storage.set_user_state('wait_wallet', chat_id)

            elif message['callback_query']['data'] == 'reject':
                self._sender.answer_callback_query(chat_id, message['callback_query']['id'], None)

                self._cancel_bet_process(chat_id, 'Действие отменено.')
            else:
                self._cancel_bet_process(chat_id, 'Не понимаю, что нужно сделать, но могу действовать в соответствии '
                                                  'со своими командами.')

        else:
            self._cancel_bet_process(chat_id, 'Не понимаю, что нужно сделать, но могу действовать в соответствии '
                                              'со своими командами.')

    def _handle_user_choice(self, chat_id, message):
        if 'callback_query' in message:
            category = message['callback_query']['data']
            self._data_storage.add_bet(chat_id, category)

            self._sender.answer_callback_query(chat_id, message['callback_query']['id'],
                                               self._data_storage.responses['5']['ru'].replace('{#1}', category))

            message_after_choice = self._data_storage.responses['39']['ru'].replace('{#1}', category) \
                .replace('{#2}', str(self._data_storage.bet_amount)) \
                .replace('{#3}', f'{self._data_storage.time_limit} GMT')

            self._sender.send_message(chat_id, message_after_choice)

            if category == 'A':
                wallet = self._data_storage.A_wallet
                qr_link = self._ether_scan.get_qr_link(self._data_storage.A_wallet)
            else:
                wallet = self._data_storage.B_wallet
                qr_link = self._ether_scan.get_qr_link(self._data_storage.B_wallet)

            self._sender.send_message(chat_id, wallet, reply_markup=json.dumps({'hide_keyboard': True}))
            self._sender.send_photo(chat_id, qr_link,
                                    reply_markup=json.dumps({'inline_keyboard': [[{'text': 'Далее',
                                                                                   'callback_data': 'next'},
                                                                                  {'text': 'Отменить',
                                                                                   'callback_data': 'reject'}]],
                                                             'resize_keyboard': True}))

            self._data_storage.set_user_state('wait_choice_after_qr', chat_id)

        elif 'message' in message and message['message']['text'] == 'Отменить':
            self._cancel_bet_process(chat_id, 'Действие отменено.')

        else:
            self._cancel_bet_process(chat_id, 'Не понимаю, что нужно сделать, но могу действовать в соответствии '
                                              'со своими командами.')

    def _handle_bet_command(self, command):
        chat_id = command['message']['from']['id']
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        announcement = self._data_storage.responses['38']['ru'] \
            .replace('{#1}', str(self._data_storage.cases_day)) \
            .replace('{#4}', str(self._data_storage.control_value)) \
            .replace('{#2}', rate_A) \
            .replace('{#3}', rate_B)\
            .replace('{#5}', str(self._data_storage.control_value + 1))\
            .replace('{#7}', str(self._data_storage.bet_amount))\
            .replace('{#6}', str(self._data_storage.time_limit))

        self._sender.send_message(chat_id, announcement, reply_markup=json.dumps({'inline_keyboard': [
            [{'text': 'A', 'callback_data': 'A'},
             {'text': 'B', 'callback_data': 'B'}]],
            'resize_keyboard': True}))

        self._sender.send_message(chat_id, 'Для отмены нажмите "Отменить".',
                                  reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                           'resize_keyboard': True}))

        self._data_storage.set_user_state('wait_choice', chat_id)

    @staticmethod
    def represent_rates(rate_A, rate_B):
        if rate_A != 'N/a' and rate_B != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(math.trunc(rate_B * 1000) / 1000)

        elif rate_A != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(rate_B)

        elif rate_B != 'N/a':
            return str(math.trunc(rate_B * 1000) / 1000), str(rate_A)

        else:
            return str(rate_A), str(rate_B)

    def _handle_start_command(self, chat_id):
        self._sender.send_message(chat_id, self._data_storage.responses['34']['ru'],
                                  reply_markup=self._data_storage.basic_keyboard)

    def _handle_help_command(self, chat_id):  # TODO: fix bug with smiles here
        message = self._data_storage.responses['36']['ru']
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        message = message.replace('{#1}', str(self._data_storage.control_value))\
                         .replace('{#2}', str(self._data_storage.control_value + 1))\
                         .replace('{#3}', rate_A)\
                         .replace('{#4}', rate_B)\
                         .replace('{#5}', str(self._data_storage.bet_amount))\
                         .replace('{#6}', str(self._data_storage.time_limit))

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_how_many_command(self, chat_id):
        cases_day, cases_all = self._data_storage.cases_day, self._data_storage.cases_total
        date = self._data_storage.date - timedelta(hours=3)

        message = self._data_storage.responses['35']['ru'].replace('{#1}', str(cases_day)) \
            .replace('{#2}', str(cases_all)).replace('{#3}', str(date))

        self._sender.send_message(chat_id, message, reply_markup=self._data_storage.basic_keyboard)

    def _handle_status_command(self, chat_id):
        bet_list = self._data_storage.get_user_bets(chat_id)
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        if len(bet_list) > 0:
            message = ''

            for n, bet in enumerate(bet_list):
                if bet['confirmed']:
                    status = self._data_storage.responses["29"]['ru']

                else:
                    status = self._data_storage.responses["30"]['ru']

                if bet['category'] == 'A':
                    rate = rate_A
                else:
                    rate = rate_B

                message += f'{self._data_storage.responses["25"]["ru"]} <b>{n + 1}</b>:' \
                           f'\n{self._data_storage.responses["26"]["ru"]}: {bet["category"]}, текущий коэффициент {rate}' \
                           f'\n{self._data_storage.responses["27"]["ru"]}: {bet["wallet"]}' \
                           f'\n{self._data_storage.responses["28"]["ru"]}: {status}\n\n'

            self._sender.send_message(chat_id, message,
                                      reply_markup=json.dumps({'keyboard': [
                                                                    [{'text': '/bet'}, {'text': '/help'}]],
                                                               'resize_keyboard': True}))
        else:
            self._sender.send_message(chat_id, self._data_storage.responses["31"]['ru'])
