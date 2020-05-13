import json
from decimal import Decimal
from datetime import timedelta
import math

from Services.DataKeeper import DataKeeper
from Services.Sender import Sender
from Services.EtherScan import EtherScan
from Services.QRGenerator import QRGenerator


# TODO: add method for new round configuring
# TODO: add time limit
# TODO: add method for result waiting (timer for check updates and requests handling in another thread)
# TODO: add three basic for requests handling threads


class CommandHandler:
    def __init__(self, access_token):
        self._info_commands = ['/start', '/help', '/how_many', '/current_round', '/status']
        self._action_commands = ['/bet', '/setLang']
        self._admin_commands = ['/set_wallet_a', '/set_wallet_b', '/set_fee', '/set_vote_end_time']
        self._data_keeper = DataKeeper()
        self._data_keeper.update()
        self._sender = Sender(access_token)
        self._ether_scan = EtherScan()
        self._qr_generator = QRGenerator()

    def update_rates(self):
        bets_A = self._data_keeper.count_bets('A')
        bets_B = self._data_keeper.count_bets('B')

        fee = self._data_keeper.get_fee()

        if bets_A:
            rate_A = ((bets_A + bets_B) / bets_A) * (1 - fee)
        else:
            rate_A = 'N/a'

        if bets_B:
            rate_B = ((bets_A + bets_B) / bets_B) * (1 - fee)
        else:
            rate_B = 'N/a'

        self._data_keeper.update_rates(rate_A, rate_B)

    def handle_text_message(self, message_object, allow_bets=True):
        chat_id = message_object['message']['from']['id']

        lang = self._data_keeper.get_lang(chat_id)
        if not lang:
            message = self._data_keeper.responses['21']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)
            return

        state = self._data_keeper.get_state(chat_id)

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

        lang = self._data_keeper.get_lang(chat_id)
        if not lang and command[0] != '/setLang':
            message = self._data_keeper.responses['21']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)
            return

        state = self._data_keeper.get_state(chat_id)

        if state:
            self._data_keeper.set_state(None, chat_id)

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
                self._howmany(chat_id)
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

            elif command[0] == '/set_lang':
                self._set_lang(chat_id, command_object)
                return

        self._sender.send(chat_id, self._data_keeper.responses['3'][lang])

    def handle_state(self, chat_id, state, message, allow_bets=True):
        if not allow_bets:
            self._sender.send(chat_id, 'Извините, время для участия в текущей игре вышло.')
            return

        lang = self._data_keeper.get_lang(chat_id)

        if not lang:
            message = self._data_keeper.responses['21']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)
            return

        if state == 'bet_0':
            if 'callback_query' in message:
                category = message['callback_query']['data']
                callback_query_id = message['callback_query']['id']
                self._data_keeper.add_bet(chat_id, category)

                self._sender.answer_callback_query(chat_id, callback_query_id, self._data_keeper.responses['5'][lang]
                                                   .replace('{#1}', category))

                message_1 = self._data_keeper.responses['39'][lang].replace('{#1}', category) \
                    .replace('{#2}', str(self._data_keeper.get_bet_amount())) \
                    .replace('{#3}', f'{self._data_keeper.get_time_limit()} GMT')

                self._sender.send(chat_id, message_1)

                if category == 'A':
                    self._sender.send(chat_id, self._data_keeper.get_A_wallet(),
                                      reply_markup=json.dumps({'hide_keyboard': True}))

                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_A_wallet())
                    self._sender.send_photo(chat_id, qr_link, reply_markup=json.dumps({'inline_keyboard':
                                                                                           [[{'text': 'Далее',
                                                                                              'callback_data': 'next'},
                                                                                            {'text': 'Отменить',
                                                                                              'callback_data': 'reject'}]],
                                                                                       'resize_keyboard': True}))

                elif category == 'B':
                    self._sender.send(chat_id, self._data_keeper.get_B_wallet(),
                                      reply_markup=json.dumps({'hide_keyboard': True}))

                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_B_wallet())

                    self._sender.send_photo(chat_id, qr_link, reply_markup=
                    json.dumps({'inline_keyboard': [[{'text': 'Далее',
                                                      'callback_data': 'next'},
                                                    {'text': 'Отменить',
                                                      'callback_data': 'reject'}]],
                                'resize_keyboard': True}))

                self._data_keeper.set_state('bet_3', chat_id)

            elif 'message' in message and message['message']['text'] == 'Отменить':
                self._data_keeper.set_state(None, chat_id)
                self._sender.send(chat_id, 'Действие отменено.',
                                  reply_markup=json.dumps({'keyboard':
                                      [
                                          [{'text': '/how_many'}, {'text': '/bet'}],
                                          [{'text': '/current_round'}, {'text': '/status'}],
                                          [{'text': '/help'}]
                                      ],
                                      'resize_keyboard': True}))

            else:
                self._data_keeper.set_state(None, chat_id)
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

        elif state == 'bet_3':
            if 'callback_query' in message:
                if message['callback_query']['data'] == 'next':
                    callback_query_id = message['callback_query']['id']
                    self._sender.answer_callback_query(chat_id, callback_query_id, '')

                    wallet = self._data_keeper.get_wallet(chat_id)

                    if not wallet:
                        message_2 = self._data_keeper.responses['7'][lang]

                        self._sender.send(chat_id, message_2,
                                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                   'resize_keyboard': True}))

                        self._data_keeper.set_state('bet_2', chat_id)
                    else:
                        message_2 = self._data_keeper.responses['20'][lang].replace('{#1}', wallet)

                        button_A = {'text': self._data_keeper.responses['8'][lang], 'callback_data': 1}
                        button_B = {'text': self._data_keeper.responses['9'][lang], 'callback_data': 0}

                        keyboard = [[button_A, button_B], [{'text': 'Отменить', 'callback_data': -1}]]

                        self._sender.send(chat_id, message_2, reply_markup=json.dumps({'inline_keyboard': keyboard,
                                                                                       'resize_keyboard': True}))
                        self._data_keeper.set_state('bet_1', chat_id)

                elif message['callback_query']['data'] == 'reject':
                    callback_query_id = message['callback_query']['id']

                    self._sender.answer_callback_query(chat_id, callback_query_id, '')

                    self._data_keeper.remove_last_bet(chat_id)
                    self._data_keeper.set_state(None, chat_id)

                    self._sender.send(chat_id, 'Действие отменено.',
                                      reply_markup=json.dumps({'keyboard':
                                          [
                                              [{'text': '/how_many'}, {'text': '/bet'}],
                                              [{'text': '/current_round'}, {'text': '/status'}],
                                              [{'text': '/help'}]
                                          ],
                                          'resize_keyboard': True}))
                else:
                    self._data_keeper.set_state(None, chat_id)
                    self._data_keeper.remove_last_bet(chat_id)
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

        elif state == 'bet_1':
            if 'callback_query' in message:
                use_previous_wallet = int(message['callback_query']['data'])
                callback_query_id = message['callback_query']['id']

                if use_previous_wallet == -1:
                    self._data_keeper.remove_last_bet(chat_id)
                    self._sender.answer_callback_query(chat_id, callback_query_id, None)
                    self._sender.send(chat_id, 'Действие отменено.', reply_markup=json.dumps({'keyboard':
                                          [
                                              [{'text': '/how_many'}, {'text': '/bet'}],
                                              [{'text': '/current_round'}, {'text': '/status'}],
                                              [{'text': '/help'}]
                                          ],
                                          'resize_keyboard': True}))
                    self._data_keeper.set_state(None, chat_id)
                    return

                elif use_previous_wallet == 1:
                    self._data_keeper.add_wallet_to_last_bet(chat_id, self._data_keeper.get_wallet(chat_id))
                    self._sender.answer_callback_query(chat_id, callback_query_id, None)

                    self._sender.send(chat_id, self._data_keeper.responses['10'][lang],
                                      reply_markup=json.dumps({'keyboard':
                                          [
                                              [{'text': '/how_many'}, {'text': '/bet'}],
                                              [{'text': '/current_round'}, {'text': '/status'}],
                                              [{'text': '/help'}]
                                          ],
                                          'resize_keyboard': True}))

                    self._data_keeper.set_state(None, chat_id)

                    # TODO: check payment and verify (or not) user's vote
                    # self.update()

                else:
                    self._sender.answer_callback_query(chat_id, callback_query_id, '')
                    self._data_keeper.set_state('bet_2', chat_id)

                    message = self._data_keeper.responses['11'][lang]
                    self._sender.send(chat_id, message,
                                      reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                               'resize_keyboard': True}))

            elif 'message' in message and message['message']['text'] == 'Отменить':
                self._sender.send(chat_id, 'Действие отменено.')

                self._data_keeper.set_state(None, chat_id)
                self._data_keeper.remove_last_bet(chat_id)
            else:
                self._data_keeper.remove_last_bet(chat_id)
                self._data_keeper.set_state(None, chat_id)
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

        elif state == 'bet_2':
            wallet = message['message']['text']

            if wallet == 'Отменить':
                self._data_keeper.set_state(None, chat_id)
                self._data_keeper.remove_last_bet(chat_id)
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
                message = self._data_keeper.responses['22'][lang]
                self._sender.send(chat_id, message)
                return

            self._data_keeper.add_wallet_to_last_bet(chat_id, wallet)

            self._data_keeper.set_wallet(wallet, chat_id)
            self._data_keeper.set_state(None, chat_id)

            success_message = self._data_keeper.responses['12'][lang]

            self._sender.send(chat_id, success_message,
                              reply_markup=json.dumps({'keyboard':
                                  [
                                      [{'text': '/how_many'}, {'text': '/bet'}],
                                      [{'text': '/current_round'}, {'text': '/status'}],
                                      [{'text': '/help'}]
                                  ],
                                  'resize_keyboard': True}))

            # TODO: check payment and verify (or not) user's vote
            self.update_rates()

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']
        lang = self._data_keeper.get_lang(chat_id)
        rate_A, rate_B = self.represent_rates(self._data_keeper.get_rate_A(), self._data_keeper.get_rate_B())

        self._data_keeper.set_state(None, chat_id)

        announcement = self._data_keeper.responses['38'][lang] \
            .replace('{#1}', str(self._data_keeper.get_date())) \
            .replace('{#2}', str(self._data_keeper.get_cases_day())) \
            .replace('{#3}', str(self._data_keeper.get_control_value())) \
            .replace('{#4}', str(self._data_keeper.get_control_value() + 1)) \
            .replace('{#5}', rate_A) \
            .replace('{#6}', rate_B) \
            .replace('{#7}', f'{self._data_keeper.get_time_limit()} GMT')

        self._sender.send(chat_id, announcement, reply_markup=json.dumps({'inline_keyboard': [
            [{'text': 'A', 'callback_data': 'A'},
             {'text': 'B', 'callback_data': 'B'}]],
            'resize_keyboard': True}))

        self._sender.send(chat_id, 'Для отмены нажмите "Отменить".',
                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                   'resize_keyboard': True}))
        self._data_keeper.set_state('bet_0', chat_id)

    @staticmethod
    def represent_rates(rate_A, rate_B):
        if rate_A != 'N/a' and rate_B != 'N/a':
            rate_A = math.trunc(rate_A * 1000) / 1000
            rate_B = math.trunc(rate_B * 1000) / 1000
            # rate_A = str(Decimal(str(rate_A)).quantize(Decimal("1.000")))
            # rate_B = str(Decimal(str(rate_B)).quantize(Decimal("1.000")))

        elif rate_A != 'N/a':
            rate_A = math.trunc(rate_A * 1000) / 1000
            rate_B = str(rate_B)

        elif rate_B != 'N/a':
            rate_B = math.trunc(rate_B * 1000) / 1000
            rate_A = str(rate_A)

        else:
            rate_A = str(rate_A)
            rate_B = str(rate_B)

        return rate_A, rate_B

    def _start(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        self._sender.send(chat_id, self._data_keeper.responses['34'][lang],
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _help(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        message = self._data_keeper.responses['36'][lang]

        self._sender.send(chat_id, message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _howmany(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        # self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date() - timedelta(hours=3)

        message = self._data_keeper.responses['35'][lang].replace('{#1}', str(cases_day)) \
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
        lang = self._data_keeper.get_lang(chat_id)
        control_value = self._data_keeper.get_control_value()
        rate_A, rate_B = self.represent_rates(self._data_keeper.get_rate_A(), self._data_keeper.get_rate_B())

        message = self._data_keeper.responses['37'][lang].replace('{#1}', str(control_value)) \
            .replace('{#2}', str(control_value + 1)) \
            .replace('{#3}', rate_A) \
            .replace('{#4}', rate_B) \
            .replace('{#5}', str(self._data_keeper.get_time_limit()))

        self._sender.send(chat_id, message,
                          reply_markup=json.dumps({'keyboard':
                              [
                                  [{'text': '/how_many'}, {'text': '/bet'}],
                                  [{'text': '/current_round'}, {'text': '/status'}],
                                  [{'text': '/help'}]
                              ],
                              'resize_keyboard': True}))

    def _set_lang(self, chat_id, message):
        lang = message['message']['text'].split()[1]

        if lang in ['en', 'ru']:
            self._data_keeper.set_lang(chat_id, lang)
            message = self._data_keeper.responses['23'][lang]
            self._sender.send(chat_id, message)
        else:
            message = self._data_keeper.responses['24']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)

    def _status(self, chat_id):
        bets = self._data_keeper.get_bets(chat_id)
        lang = self._data_keeper.get_lang(chat_id)

        if len(bets) > 0:
            message = ''

            for n, bet in enumerate(bets):
                if bet['confirmed']:
                    status = self._data_keeper.responses["29"][lang]
                else:
                    status = self._data_keeper.responses["30"][lang]

                message += f'{self._data_keeper.responses["25"][lang]} <b>{n + 1}</b>:' \
                           f'\n{self._data_keeper.responses["26"][lang]}: {bet["category"]}' \
                           f'\n{self._data_keeper.responses["27"][lang]}: {bet["wallet"]}' \
                           f'\n{self._data_keeper.responses["28"][lang]}: {status}' \
                           f'\nID: {bet["bet_id"]}\n\n'

            self._sender.send(chat_id, message,
                              reply_markup=json.dumps({'keyboard': [[{'text': '/bet'}, {'text': '/help'}],
                                                                    [{'text': '/current_round'}]],
                                                       'resize_keyboard': True}))
        else:
            self._sender.send(chat_id, self._data_keeper.responses["31"][lang])
