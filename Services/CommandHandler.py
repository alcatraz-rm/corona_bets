import json
from datetime import timedelta
import math

from Services.Sender import Sender
from Services.EtherScan import EtherScan
from Services.QRGenerator import QRGenerator
from Services.DataStorage import DataStorage


# TODO: add method for new round configuring
# TODO: add time limit
# TODO: add method for result waiting (timer for check updates and requests handling in another thread)
# TODO: add three basic for requests handling threads


class CommandHandler:
    def __init__(self, access_token):
        self._info_commands = ['/start', '/help', '/how_many', '/current_round', '/status']
        self._action_commands = ['/bet', '/setLang']
        self._admin_commands = ['/set_wallet_a', '/set_wallet_b', '/set_fee', '/set_vote_end_time']

        self._data_storage = DataStorage()

        self._data_storage.update_statistics()

        self._sender = Sender(access_token)
        self._ether_scan = EtherScan()
        self._qr_generator = QRGenerator()

    def handle_text_message(self, message_object, allow_bets=True):
        chat_id = message_object['message']['from']['id']
        state = self._data_storage.get_state(chat_id)

        if state:
            self.handle_state(chat_id, state, message_object, allow_bets)
            return

        self._sender.send(chat_id, 'Не понимаю, что нужно сделать, '
                                   'но могу действовать в соответствии со своими командами',
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def handle_command(self, command_object, allow_bets):
        chat_id = command_object['message']['from']['id']
        command = command_object['message']['text'].split()

        state = self._data_storage.get_state(chat_id)

        if state:
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Не понимаю, что нужно сделать, '
                                       'но могу действовать в соответствии со своими командами',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

        if command[0] in self._info_commands:
            if command[0] == '/start':
                self._start(chat_id)
                return

            elif command[0] == '/help':
                self._help(chat_id)
                return

            elif command[0] == '/how_many':
                self._how_many(chat_id)
                return

            elif command[0] == '/current_round':
                self._current_round(chat_id)
                return

            elif command[0] == '/status':
                self._status(chat_id)
                return

        if command[0] in self._action_commands:
            if command[0] == '/bet':
                if allow_bets:
                    self._bet(command_object)
                    return
                else:
                    self._sender.send(chat_id, 'Извините, время для участия в текущей игре вышло.')
                    return

        self._sender.send(chat_id, self._data_storage.responses['3']['ru'])

    def handle_state(self, chat_id, state, message, allow_bets=True):
        if not allow_bets:
            self._sender.send(chat_id, 'Извините, время для участия в текущей игре вышло.')
            return

        if state == 'wait_choice':
            self._handle_choice(chat_id, message)

        elif state == 'wait_choice_after_qr':
            self._handle_choice_after_qr(chat_id, message)

        elif state == 'use_previous_wallet?':
            self._handle_wallet_choice(chat_id, message)

        elif state == 'wait_wallet':
            self._handle_wallet(chat_id, message)

    def _handle_wallet_choice(self, chat_id, message):
        if 'callback_query' in message:
            use_previous_wallet = int(message['callback_query']['data'])
            callback_query_id = message['callback_query']['id']

            if use_previous_wallet == -1:
                self._data_storage.remove_last_bet(chat_id)

                self._sender.answer_callback_query(chat_id, callback_query_id, None)
                self._sender.send(chat_id, 'Действие отменено.', reply_markup=json.dumps({'keyboard':
                    [
                        [{'text': '/how_many'}, {'text': '/bet'}],
                        [{'text': '/current_round'}, {'text': '/status'}],
                        [{'text': '/help'}]
                    ],
                    'resize_keyboard': True}))
                self._data_storage.set_state(None, chat_id)
                return

            elif use_previous_wallet == 1:
                self._data_storage.add_wallet_to_last_bet(chat_id, self._data_storage.get_last_wallet(chat_id))
                self._sender.answer_callback_query(chat_id, callback_query_id, None)

                self._sender.send(chat_id, self._data_storage.responses['10']['ru'],
                                  reply_markup=json.dumps({'keyboard':
                                      [
                                          [{'text': '/how_many'}, {'text': '/bet'}],
                                          [{'text': '/current_round'}, {'text': '/status'}],
                                          [{'text': '/help'}]
                                      ],
                                      'resize_keyboard': True}))

                self._data_storage.set_state(None, chat_id)

                # TODO: check payment and verify (or not) user's vote

            else:
                self._sender.answer_callback_query(chat_id, callback_query_id, '')
                self._data_storage.set_state('wait_wallet', chat_id)

                message = self._data_storage.responses['11']['ru']

                self._sender.send(chat_id, message,
                                  reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                           'resize_keyboard': True}))

        elif 'message' in message and message['message']['text'] == 'Отменить':
            self._sender.send(chat_id, 'Действие отменено.')

            self._data_storage.remove_last_bet(chat_id)
            self._data_storage.set_state(None, chat_id)

        else:
            self._data_storage.remove_last_bet(chat_id)
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Я, к сожалению, умею выполнять только команды ниже :)\nВсегда можешь '
                                       'посмотреть, что я умею по команде /help.',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

    def _handle_wallet(self, chat_id, message):
        wallet = message['message']['text']

        if wallet == 'Отменить':
            self._data_storage.remove_last_bet(chat_id)
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Действие отменено.',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

        if not self._ether_scan.wallet_is_correct(wallet):
            message = self._data_storage.responses['22']['ru']

            self._sender.send(chat_id, message)
            return

        self._data_storage.add_wallet_to_last_bet(chat_id, wallet)
        self._data_storage.set_state(None, chat_id)

        success_message = self._data_storage.responses['12']['ru']

        self._sender.send(chat_id, success_message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

        # TODO: check payment and verify (or not) user's vote

    def _handle_choice_after_qr(self, chat_id, message):
        if 'callback_query' in message:
            if message['callback_query']['data'] == 'next':
                callback_query_id = message['callback_query']['id']
                self._sender.answer_callback_query(chat_id, callback_query_id, '')

                wallet = self._data_storage.get_last_wallet(chat_id)

                if not wallet:
                    message_2 = self._data_storage.responses['7']['ru']

                    self._sender.send(chat_id, message_2,
                                      reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                               'resize_keyboard': True}))

                    self._data_storage.set_state('wait_wallet', chat_id)
                else:
                    message_2 = self._data_storage.responses['20']['ru'].replace('{#1}', wallet)

                    keyboard = [[{'text': self._data_storage.responses['8']['ru'], 'callback_data': 1},
                                 {'text': self._data_storage.responses['9']['ru'], 'callback_data': 0}],
                                [{'text': 'Отменить', 'callback_data': -1}]]

                    self._sender.send(chat_id, message_2, reply_markup=json.dumps({'inline_keyboard': keyboard,
                                                                                   'resize_keyboard': True}))
                    self._data_storage.set_state('use_previous_wallet?', chat_id)

            elif message['callback_query']['data'] == 'reject':
                callback_query_id = message['callback_query']['id']

                self._sender.answer_callback_query(chat_id, callback_query_id, '')

                self._data_storage.remove_last_bet(chat_id)
                self._data_storage.set_state(None, chat_id)

                self._sender.send(chat_id, 'Действие отменено.',
                                  reply_markup=json.dumps({'keyboard':
                                      [
                                          [{'text': '/how_many'}, {'text': '/bet'}],
                                          [{'text': '/current_round'}, {'text': '/status'}],
                                          [{'text': '/help'}]
                                      ],
                                      'resize_keyboard': True}))
            else:
                self._data_storage.remove_last_bet(chat_id)
                self._data_storage.set_state(None, chat_id)

                self._sender.send(chat_id, 'Не понимаю, что нужно сделать, '
                                           'но могу действовать в соответствии со своими командами',
                                  reply_markup=json.dumps({'keyboard':
                                      [
                                          [{'text': '/how_many'}, {'text': '/bet'}],
                                          [{'text': '/current_round'}, {'text': '/status'}],
                                          [{'text': '/help'}]
                                      ],
                                      'resize_keyboard': True}))
                return

        else:
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Не понимаю, что нужно сделать, '
                                       'но могу действовать в соответствии со своими командами',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

    def _handle_choice(self, chat_id, message):
        if 'callback_query' in message:
            category = message['callback_query']['data']
            callback_query_id = message['callback_query']['id']
            self._data_storage.add_bet(chat_id, category)

            self._sender.answer_callback_query(chat_id, callback_query_id, self._data_storage.responses['5']['ru']
                                               .replace('{#1}', category))

            choice_message = self._data_storage.responses['39']['ru'].replace('{#1}', category) \
                .replace('{#2}', str(self._data_storage.bet_amount)) \
                .replace('{#3}', f'{self._data_storage.time_limit} GMT')

            self._sender.send(chat_id, choice_message)

            if category == 'A':
                wallet = self._data_storage.A_wallet
                qr_link = self._qr_generator.generate_qr(self._data_storage.A_wallet)
            else:
                wallet = self._data_storage.B_wallet
                qr_link = self._qr_generator.generate_qr(self._data_storage.B_wallet)

            self._sender.send(chat_id, wallet, reply_markup=json.dumps({'hide_keyboard': True}))
            self._sender.send_photo(chat_id, qr_link,
                                    reply_markup=json.dumps({'inline_keyboard': [[{'text': 'Далее',
                                                                                   'callback_data': 'next'},
                                                                                  {'text': 'Отменить',
                                                                                   'callback_data': 'reject'}]],
                                                             'resize_keyboard': True}))

            self._data_storage.set_state('wait_choice_after_qr', chat_id)

        elif 'message' in message and message['message']['text'] == 'Отменить':
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Действие отменено.',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

        else:
            self._data_storage.set_state(None, chat_id)

            self._sender.send(chat_id, 'Не понимаю, что нужно сделать, '
                                       'но могу действовать в соответствии со своими командами',
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))
            return

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']
        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        announcement = self._data_storage.responses['38']['ru'] \
            .replace('{#1}', str(self._data_storage.date)) \
            .replace('{#2}', str(self._data_storage.cases_day)) \
            .replace('{#3}', str(self._data_storage.control_value)) \
            .replace('{#4}', str(self._data_storage.control_value + 1)) \
            .replace('{#5}', rate_A) \
            .replace('{#6}', rate_B) \
            .replace('{#7}', f'{self._data_storage.time_limit} GMT')

        self._sender.send(chat_id, announcement, reply_markup=json.dumps({'inline_keyboard': [
            [{'text': 'A', 'callback_data': 'A'},
             {'text': 'B', 'callback_data': 'B'}]],
            'resize_keyboard': True}))

        self._sender.send(chat_id, 'Для отмены нажмите "Отменить".',
                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                   'resize_keyboard': True}))

        self._data_storage.set_state('wait_choice', chat_id)

    @staticmethod
    def represent_rates(rate_A, rate_B):
        if rate_A != 'N/a' and rate_B != 'N/a':
            rate_A = str(math.trunc(rate_A * 1000) / 1000)
            rate_B = str(math.trunc(rate_B * 1000) / 1000)

        elif rate_A != 'N/a':
            rate_A = str(math.trunc(rate_A * 1000) / 1000)
            rate_B = str(rate_B)

        elif rate_B != 'N/a':
            rate_B = str(math.trunc(rate_B * 1000) / 1000)
            rate_A = str(rate_A)

        else:
            rate_A = str(rate_A)
            rate_B = str(rate_B)

        return rate_A, rate_B

    def _start(self, chat_id):
        self._sender.send(chat_id, self._data_storage.responses['34']['ru'],
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _help(self, chat_id):
        message = self._data_storage.responses['36']['ru']

        self._sender.send(chat_id, message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _how_many(self, chat_id):
        cases_day, cases_all = self._data_storage.cases_day, self._data_storage.cases_total
        date = self._data_storage.date - timedelta(hours=3)

        message = self._data_storage.responses['35']['ru'].replace('{#1}', str(cases_day)) \
            .replace('{#2}', str(cases_all)).replace('{#3}', f'{date} GMT')

        self._sender.send(chat_id, message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _current_round(self, chat_id):
        control_value = self._data_storage.control_value

        rate_A, rate_B = self.represent_rates(self._data_storage.rate_A, self._data_storage.rate_B)

        message = self._data_storage.responses['37']['ru'].replace('{#1}', str(control_value)) \
            .replace('{#2}', str(control_value + 1)) \
            .replace('{#3}', rate_A) \
            .replace('{#4}', rate_B) \
            .replace('{#5}', f"{self._data_storage.time_limit} GMT")

        self._sender.send(chat_id, message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _status(self, chat_id):
        bets = self._data_storage.get_bets(chat_id)

        if len(bets) > 0:
            message = ''

            for n, bet in enumerate(bets):
                if bet['confirmed']:
                    status = self._data_storage.responses["29"]['ru']

                else:
                    status = self._data_storage.responses["30"]['ru']

                message += f'{self._data_storage.responses["25"]["ru"]} <b>{n + 1}</b>:' \
                           f'\n{self._data_storage.responses["26"]["ru"]}: {bet["category"]}' \
                           f'\n{self._data_storage.responses["27"]["ru"]}: {bet["wallet"]}' \
                           f'\n{self._data_storage.responses["28"]["ru"]}: {status}' \
                           f'\nID: {bet["bet_id"]}\n\n'

            self._sender.send(chat_id, message,
                              reply_markup=json.dumps({'keyboard': [[{'text': '/bet'}, {'text': '/help'}],
                                                                    [{'text': '/current_round'}]],
                                                       'resize_keyboard': True}))
        else:
            self._sender.send(chat_id, self._data_storage.responses["31"]['ru'])
