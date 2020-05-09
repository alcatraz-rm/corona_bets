import json

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

    def _get_announcement(self, lang):
        return self._data_keeper.responses['4'][lang] \
            .replace('{#1}', self._data_keeper.get_date().isoformat(sep=' ')) \
            .replace('{#2}', str(self._data_keeper.get_cases_day()))

    def _update(self):
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

    def handle_text_message(self, message_object):
        chat_id = message_object['message']['from']['id']

        lang = self._data_keeper.get_lang(chat_id)
        if not lang:
            message = self._data_keeper.responses['21']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)
            return

        state = self._data_keeper.get_state(chat_id)

        if state:
            self.handle_state(chat_id, state, message_object)
            return

        self._sender.send(chat_id, self._data_keeper.responses['1'][lang])

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
            self._sender.send(chat_id, 'Пожалуйста, закончите ставку.')
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

            elif command[0] == '/set_lang':
                self._set_lang(chat_id, command_object)
                return

        self._sender.send(chat_id, self._data_keeper.responses['3'][lang])

    def handle_state(self, chat_id, state, message):
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

                message_1 = self._data_keeper.responses['39'][lang].replace('{#1}', category)\
                    .replace('{#2}', str(self._data_keeper.get_bet_amount())) \
                    .replace('{#3}', str(self._data_keeper.get_time_limit()))

                self._sender.send(chat_id, message_1)

                if category == 'A':
                    self._sender.send(chat_id, self._data_keeper.get_A_wallet(),
                                      reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}, {'text': 'Далее'}]],
                                                               'resize_keyboard': True}))

                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_A_wallet())
                    self._sender.send_photo(chat_id, qr_link)

                elif category == 'B':
                    self._sender.send(chat_id, self._data_keeper.get_B_wallet(),
                                      reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}, {'text': 'Далее'}]],
                                                               'resize_keyboard': True}))

                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_B_wallet())
                    self._sender.send_photo(chat_id, qr_link)

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
            if message['message']['text'] == 'Далее':
                wallet = self._data_keeper.get_wallet(chat_id)

                if not wallet:
                    message_2 = self._data_keeper.responses['7'][lang]

                    self._sender.send(chat_id, message_2, reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                                                   'resize_keyboard': True}))

                    self._data_keeper.set_state('bet_2', chat_id)
                else:
                    message_2 = self._data_keeper.responses['20'][lang].replace('{#1}', wallet)

                    button_A = [{'text': self._data_keeper.responses['8'][lang], 'callback_data': 1}]
                    button_B = [{'text': self._data_keeper.responses['9'][lang], 'callback_data': 0}]

                    keyboard = [button_A, button_B]

                    self._sender.send(chat_id, message_2, reply_markup=json.dumps({'inline_keyboard': keyboard,
                                                                                   'resize_keyboard': True}))
                    self._data_keeper.set_state('bet_1', chat_id)

            elif message['message']['text'] == 'Отменить':
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

                if use_previous_wallet:
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
                    self._update()

                else:
                    self._sender.answer_callback_query(chat_id, callback_query_id, '')
                    self._data_keeper.set_state('bet_2', chat_id)

                    message = self._data_keeper.responses['11'][lang]
                    self._sender.send(chat_id, message,
                                      reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                               'resize_keyboard': True}))
            else:
                self._data_keeper.remove_last_bet(chat_id)
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
            self._update()

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']
        lang = self._data_keeper.get_lang(chat_id)

        self._data_keeper.set_state(None, chat_id)

        button_A = [{'text': 'A', 'callback_data': 'A'}]
        button_B = [{'text': 'B', 'callback_data': 'B'}]

        keyboard = [button_A, button_B]

        announcement = self._data_keeper.responses['38'][lang] \
            .replace('{#1}', str(self._data_keeper.get_date())) \
            .replace('{#2}', str(self._data_keeper.get_cases_day())) \
            .replace('{#3}', str(self._data_keeper.get_control_value())) \
            .replace('{#4}', str(self._data_keeper.get_control_value() + 1)) \
            .replace('{#5}', str(self._data_keeper.get_rate_A())) \
            .replace('{#6}', str(self._data_keeper.get_rate_B())) \
            .replace('{#7}', str(self._data_keeper.get_time_limit()))

        self._sender.send(chat_id, announcement, reply_markup=json.dumps({
                                                                            'inline_keyboard': keyboard,
                                                                            'resize_keyboard': True}))

        self._sender.send(chat_id, 'Для отмены нажмите "Отменить".',
                          reply_markup=json.dumps({'keyboard': [[{'text': 'Отменить'}]],
                                                   'resize_keyboard': True}))
        self._data_keeper.set_state('bet_0', chat_id)

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

        self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date()

        message = self._data_keeper.responses['35'][lang].replace('{#1}', str(cases_day)) \
            .replace('{#2}', str(cases_all)).replace('{#3}', str(date))

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

        message = self._data_keeper.responses['37'][lang].replace('{#1}', str(control_value)) \
            .replace('{#2}', str(control_value + 1)) \
            .replace('{#3}', str(self._data_keeper.get_rate_A())) \
            .replace('{#4}', str(self._data_keeper.get_rate_B())) \
            .replace('{#5}', self._data_keeper.get_time_limit())

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
                           f'\n{self._data_keeper.responses["28"][lang]}: {status}\n\n'

            self._sender.send(chat_id, message,
                              reply_markup=json.dumps({'keyboard': [[{'text': '/bet'}, {'text': '/help'}]],
                                                       'resize_keyboard': True}))
        else:
            self._sender.send(chat_id, self._data_keeper.responses["31"][lang])
