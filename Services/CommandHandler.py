import json

from Services.DataKeeper import DataKeeper
from Services.Sender import Sender
from Services.EtherScan import EtherScan
from Services.QRGenerator import QRGenerator


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

        print(rate_A, rate_B)
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

    def handle_command(self, command_object):
        chat_id = command_object['message']['from']['id']
        command = command_object['message']['text'].split()

        lang = self._data_keeper.get_lang(chat_id)
        if not lang and command[0] != '/setLang':
            message = self._data_keeper.responses['21']['ru']
            # TODO: add the same message in eng
            self._sender.send(chat_id, message)
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
                self._bet(command_object)
                return

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

                message_1 = self._data_keeper.responses['6'][lang].replace('{#1}', category).replace('{#2}', category)

                self._sender.send(chat_id, message_1)

                if category == 'A':
                    self._sender.send(chat_id, self._data_keeper.get_A_wallet())
                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_A_wallet())
                    self._sender.send_photo(chat_id, qr_link)

                elif category == 'B':
                    self._sender.send(chat_id, self._data_keeper.get_B_wallet())
                    qr_link = self._qr_generator.generate_qr(self._data_keeper.get_B_wallet())
                    self._sender.send_photo(chat_id, qr_link)

                wallet = self._data_keeper.get_wallet(chat_id)

                if not wallet:
                    message_2 = self._data_keeper.responses['7'][lang]

                    self._sender.send(chat_id, message_2, reply_keyboard_hide=True)

                    self._data_keeper.set_state('bet_2', chat_id)
                else:
                    message_2 = self._data_keeper.responses['20'][lang].replace('{#1}', wallet)

                    button_A = [{'text': self._data_keeper.responses['8'][lang], 'callback_data': 1}]
                    button_B = [{'text': self._data_keeper.responses['9'][lang], 'callback_data': 0}]

                    keyboard = [button_A, button_B]

                    self._sender.send_with_reply_markup(chat_id, message_2, keyboard)
                    self._data_keeper.set_state('bet_1', chat_id)

        elif state == 'bet_1':
            use_previous_wallet = int(message['callback_query']['data'])
            callback_query_id = message['callback_query']['id']

            if use_previous_wallet:
                self._data_keeper.add_wallet_to_last_bet(chat_id, self._data_keeper.get_wallet(chat_id))
                self._sender.answer_callback_query(chat_id, callback_query_id, self._data_keeper.responses['10'][lang])

                self._data_keeper.set_state(None, chat_id)

                # TODO: check payment and verify (or not) user's vote
                self._update()

            else:
                self._sender.answer_callback_query(chat_id, callback_query_id, '')
                self._data_keeper.set_state('bet_2', chat_id)

                message = self._data_keeper.responses['11'][lang]
                self._sender.send(chat_id, message, reply_keyboard_hide=True)

        elif state == 'bet_2':
            wallet = message['message']['text']

            if not self._ether_scan.wallet_is_correct(wallet):
                message = self._data_keeper.responses['22'][lang]
                self._sender.send(chat_id, message)
                return

            self._data_keeper.add_wallet_to_last_bet(chat_id, wallet)

            self._data_keeper.set_wallet(wallet, chat_id)
            self._data_keeper.set_state(None, chat_id)

            success_message = self._data_keeper.responses['12'][lang]
            self._sender.send_reply_keyboard(chat_id, success_message)

            # TODO: check payment and verify (or not) user's vote
            self._update()

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']
        lang = self._data_keeper.get_lang(chat_id)

        self._data_keeper.set_state(None, chat_id)

        button_A = [{'text': 'A', 'callback_data': 'A'}]
        button_B = [{'text': 'B', 'callback_data': 'B'}]

        keyboard = [button_A, button_B]

        self._sender.send_with_reply_markup(chat_id, self._get_announcement(lang), keyboard)
        self._data_keeper.set_state('bet_0', chat_id)

    def _start(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        self._sender.send_reply_keyboard(chat_id, self._data_keeper.responses['34'][lang])

    def _help(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        message = self._data_keeper.responses['36'][lang]

        self._sender.send(chat_id, message)

    def _howmany(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)

        self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date()

        message = self._data_keeper.responses['35'][lang].replace('{#1}', str(cases_day))\
                                                         .replace('{#2}', str(cases_all)).replace('{#3}', str(date))

        self._sender.send(chat_id, message)

    def _current_round(self, chat_id):
        lang = self._data_keeper.get_lang(chat_id)
        control_value = self._data_keeper.get_control_value()

        message = self._data_keeper.responses['37'][lang].replace('{#1}', str(control_value))\
                                                         .replace('{#2}', str(control_value + 1))\
                                                         .replace('{#3}', str(self._data_keeper.get_rate_A()))\
                                                         .replace('{#4}', str(self._data_keeper.get_rate_B()))\
                                                         .replace('{#5}', self._data_keeper.get_time_limit())

        # message = f"A: {self._data_keeper.responses['2'][lang]} <= y\n" \
        #           f"B: {self._data_keeper.responses['2'][lang]} >= (y+1)\n\n" \
        #           f"{self._data_keeper.responses['19'][lang]} A: {self._data_keeper.get_rate_A()}\n" \
        #           f"{self._data_keeper.responses['19'][lang]} B: {self._data_keeper.get_rate_B()}"

        self._sender.send(chat_id, message)

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

                message += f'{self._data_keeper.responses["25"][lang]} {n + 1}:' \
                           f'\n    {self._data_keeper.responses["26"][lang]}: {bet["category"]}' \
                           f'\n    {self._data_keeper.responses["27"][lang]}: {bet["wallet"]}' \
                           f'\n    {self._data_keeper.responses["28"][lang]}: {status}\n\n'

            self._sender.send(chat_id, message)
        else:
            self._sender.send(chat_id, self._data_keeper.responses["31"][lang])
