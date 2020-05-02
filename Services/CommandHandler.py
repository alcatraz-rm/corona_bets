import json

from Services.DataKeeper import DataKeeper
from Services.Sender import Sender


class CommandHandler:
    def __init__(self, access_token):
        self._info_commands = ['/start', '/help', '/howmany', '/rate']
        self._action_commands = ['/bet', '/change_wallet', '/set_lang']
        self._data_keeper = DataKeeper()
        self._data_keeper.update()
        self._default_answer = self._data_keeper.responses['3']['ru']
        self._sender = Sender(access_token)

        self._announcement = self._data_keeper.responses['4']['ru']\
            .replace('{#1}', self._data_keeper.get_date().isoformat(sep=' '))\
            .replace('{#2}', str(self._data_keeper.get_cases_day()))

    def _update_announcement(self):
        self._announcement = self._data_keeper.responses['4']['ru']\
            .replace('{#1}', self._data_keeper.get_date().isoformat(sep=' '))\
            .replace('{#2}', self._data_keeper.get_cases_day())

    def _update(self):
        users_A = self._data_keeper.get_users('A')
        users_B = self._data_keeper.get_users('B')
        fee = self._data_keeper.get_fee()

        rate_A = ((len(users_A) + len(users_B)) / len(users_A)) * (1 - fee)
        rate_B = ((len(users_A) + len(users_B)) / len(users_B)) * (1 - fee)

        self._data_keeper.update_rates(rate_A, rate_B)

    def handle_text_message(self, message_object):
        chat_id = message_object['message']['from']['id']
        state = self._data_keeper.get_state(chat_id)

        if state:
            self.handle_state(chat_id, state, message_object)
            return

        self._sender.send(chat_id, self._data_keeper.responses['1']['ru'])

    def handle_command(self, command_object):
        command = command_object['message']['text']
        chat_id = command_object['message']['from']['id']

        if command in self._info_commands:
            if command == '/start':
                self._start(chat_id)
                return

            elif command == '/help':
                self._help(chat_id)
                return

            elif command == '/howmany':
                self._howmany(chat_id)
                return

            elif command == '/rate':
                self._rate(chat_id)
                return

        if command in self._action_commands:
            if command == '/bet':
                self._bet(command_object)
                return
            elif command == '/change_wallet':
                self._change_wallet(chat_id)
                return

        self._sender.send(chat_id, self._default_answer)

    def handle_state(self, chat_id, state, message):
        if state == 'bet_0':
            if 'callback_query' in message:
                category = message['callback_query']['data']
                callback_query_id = message['callback_query']['id']
                self._data_keeper.set_category(chat_id, category)

                self._sender.answer_callback_query(chat_id, callback_query_id, self._data_keeper.responses['5']['ru']
                                                   .replace('{#1}', category))

                message_1 = self._data_keeper.responses['6']['ru'].replace('{#1}', category).replace('{#2}', category)

                self._sender.send(chat_id, message_1)

                if category == 'A':
                    self._sender.send(chat_id, self._data_keeper.get_A_wallet())
                elif category == 'B':
                    self._sender.send(chat_id, self._data_keeper.get_B_wallet())

                wallet = self._data_keeper.get_wallet(chat_id)

                if not wallet:
                    message_2 = self._data_keeper.responses['7']['ru']

                    self._sender.send(chat_id, message_2)

                    self._data_keeper.set_state('bet_2', chat_id)
                else:
                    message_2 = self._data_keeper.responses['20']['ru'].replace('{#1}', wallet)

                    button_A = [{'text': self._data_keeper.responses['8']['ru'], 'callback_data': 1}]
                    button_B = [{'text': self._data_keeper.responses['9']['ru'], 'callback_data': 0}]

                    keyboard = [button_A, button_B]

                    self._sender.send_with_reply_markup(chat_id, message_2, keyboard)
                    self._data_keeper.set_state('bet_1', chat_id)

        elif state == 'bet_1':
            use_previous_wallet = int(message['callback_query']['data'])
            callback_query_id = message['callback_query']['id']

            if use_previous_wallet:
                self._sender.answer_callback_query(chat_id, callback_query_id, self._data_keeper.responses['10']['ru'])
                self._data_keeper.set_state(None, chat_id)

                # TODO: check payment and verify (or not) user's vote

            else:
                self._sender.answer_callback_query(chat_id, callback_query_id, '')
                self._data_keeper.set_state('bet_2', chat_id)

                message = self._data_keeper.responses['11']['ru']
                self._sender.send(chat_id, message)

        elif state == 'bet_2':
            wallet = message['message']['text']
            # TODO: check wallet

            self._data_keeper.set_wallet(wallet, chat_id)
            self._data_keeper.set_state(None, chat_id)

            success_message = self._data_keeper.responses['12']['ru']
            self._sender.send(chat_id, success_message)

            # TODO: check payment and verify (or not) user's vote

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']

        self._data_keeper.set_state(None, chat_id)

        button_A = [{'text': 'A', 'callback_data': 'A'}]
        button_B = [{'text': 'B', 'callback_data': 'B'}]

        keyboard = [button_A, button_B]

        self._sender.send_with_reply_markup(chat_id, self._announcement, keyboard)
        self._data_keeper.set_state('bet_0', chat_id)

    def _start(self, chat_id):
        # TODO: write start message
        self._sender.send(chat_id, self._data_keeper.responses['13']['ru'])

    def _help(self, chat_id):
        self._sender.send(chat_id, f'{self._data_keeper.responses["14"]["ru"]}: /howmany\n'
                                   f'{self._data_keeper.responses["15"]["ru"]}: /rate')

    def _howmany(self, chat_id):
        self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date()

        message = f'\n{self._data_keeper.responses["16"]["ru"]}: {cases_day}\n' \
                  f'{self._data_keeper.responses["17"]["ru"]}: {cases_all}\n' \
                  f'{self._data_keeper.responses["18"]["ru"]}: {date.isoformat(sep=" ")}'

        self._sender.send(chat_id, message)

    def _rate(self, chat_id):
        message = f"A: {self._data_keeper.responses['2']['ru']} <= y\n" \
                  f"B: {self._data_keeper.responses['2']['ru']} >= (y+1)\n\n"\
                  f"{self._data_keeper.responses['19']['ru']} A: {self._data_keeper.get_rate_A()}\n"\
                  f"{self._data_keeper.responses['19']['ru']} B: {self._data_keeper.get_rate_B()}"

        self._sender.send(chat_id, message)

    def _change_wallet(self, chat_id):
        self._data_keeper.set_state('bet_2', chat_id)

        message = self._data_keeper.responses['11']['ru']
        self._sender.send(chat_id, message)
