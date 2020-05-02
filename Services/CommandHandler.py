from Services.DataKeeper import DataKeeper
from Services.Sender import Sender


class CommandHandler:
    def __init__(self, access_token):
        self._info_commands = ['/start', '/help', '/howmany', '/rate']
        self._action_commands = ['/bet']
        self._default_answer = "Sorry, I don't know this command."
        self._sender = Sender(access_token)
        self._data_keeper = DataKeeper()
        self._data_keeper.update()

        self._announcement = f"Количество заболевших по состоянию на " \
                             f"{self._data_keeper.get_date().isoformat(sep=' ')}: {self._data_keeper.get_cases_day()}\n" \
                             f"Сейчас открыто голосование на результаты завтрашнего дня.\n\n" \
                             f"A: заболевших будет <= y\nB: заболевших будет >= (y+1)\n\n" \
                             f"Для голосования необходимо выбрать вариант кнопкой ниже (А или B). " \
                             f"После выбора необходимо подтвердить свой голос переводом ETH " \
                             f"и вводом своего кошелька отправления."

    def _update_announcement(self):
        self._announcement = f"Количество заболевших по состоянию на " \
                             f"{self._data_keeper.get_date().isoformat(sep=' ')}: {self._data_keeper.get_cases_day()}\n" \
                             f"Сейчас открыто голосование на результаты завтрашнего дня.\n\n" \
                             f"A: заболевших будет <= y\nB: заболевших будет >= (y+1)\n\n" \
                             f"Для голосования необходимо выбрать вариант кнопкой ниже (А или B). " \
                             f"После выбора необходимо подтвердить свой голос переводом ETH " \
                             f"и вводом (подтверждением) своего кошелька отправления."

    def handle_text_message(self, message_object):
        chat_id = message_object['message']['from']['id']
        state = self._data_keeper.get_state(chat_id)

        if state:
            self.handle_state(chat_id, state, message_object)
            return

        self._sender.send(chat_id, "Hello!")

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

        self._sender.send(chat_id, self._default_answer)

    def handle_state(self, chat_id, state, message):
        if state == 'bet_0':
            if 'callback_query' in message:
                category = message['callback_query']['data']
                callback_query_id = message['callback_query']['id']
                self._data_keeper.set_category(chat_id, category)

                self._sender.answer_callback_query(chat_id, callback_query_id, f'Вы проголосовали за вариант '
                                                                               f'{category}.')

                message_1 = f'Выбран вариант {category}.\nДля подтверждения, пожалуйста, сделайте перевод ETH на адрес ' \
                            f'варианта {category}.' \
                            '\n\nQR\n\n' \
                            'Сумма: z\n\n' \
                            'Отправляемая сумма должна быть в точности равной z. Mining fee уплачивается ' \
                            'отправителем самостоятельно. В противном случае голос не будет учтен. ' \
                            'Отправленная сумма вернется обратно отправителю за вычетом mining fee в течение 2 дней.'

                self._sender.send(chat_id, message_1)

                if category == 'A':
                    self._sender.send(chat_id, self._data_keeper.get_A_wallet())
                elif category == 'B':
                    self._sender.send(chat_id, self._data_keeper.get_B_wallet())

                wallet = self._data_keeper.get_wallet(chat_id)

                if not wallet:
                    message_2 = 'Для подтверждения голоса необходимо не только сделать перевод, но и ввести свой адрес ' \
                                'кошелька, который должен соответствовать адресу отправления.\nПожалуйста, введите ' \
                                'действительный адрес эфир-кошелька в ответ на это сообщение.'

                    self._sender.send(chat_id, message_2)

                    self._data_keeper.set_state('bet_2', chat_id)
                else:
                    message_2 = f'Использовать кошелек {wallet}?'
                    button_A = [{'text': 'Да', 'callback_data': 1}]
                    button_B = [{'text': 'Нет, изменить данные кошелька', 'callback_data': 0}]

                    keyboard = [button_A, button_B]

                    self._sender.send_with_reply_markup(chat_id, message_2, keyboard)
                    self._data_keeper.set_state('bet_1', chat_id)

        elif state == 'bet_1':
            use_previous_wallet = int(message['callback_query']['data'])
            callback_query_id = message['callback_query']['id']

            if use_previous_wallet:
                self._sender.answer_callback_query(chat_id, callback_query_id, 'Используется предыдущий кошелек.')
                self._data_keeper.set_state(None, chat_id)

                # ok, here we need to check payment and verify (or not) user's vote

            else:
                self._sender.answer_callback_query(chat_id, callback_query_id, '')
                self._data_keeper.set_state('bet_2', chat_id)

                message = 'Пожалуйста, введите действительный адрес эфир-кошелька в ответ на это сообщение.'
                self._sender.send(chat_id, message)

        elif state == 'bet_2':
            wallet = message['message']['text']
            # check wallet

            self._data_keeper.set_wallet(wallet, chat_id)
            self._data_keeper.set_state(None, chat_id)

            success_message = 'Данные кошелька успешно изменены.'
            self._sender.send(chat_id, success_message)

            # ok, here we need to check payment and verify (or not) user's vote

    def _bet(self, command_object):
        chat_id = command_object['message']['from']['id']

        self._data_keeper.set_state(None, chat_id)

        button_A = [{'text': 'A', 'callback_data': 'A'}]
        button_B = [{'text': 'B', 'callback_data': 'B'}]

        keyboard = [button_A, button_B]

        self._sender.send_with_reply_markup(chat_id, self._announcement, keyboard)
        self._data_keeper.set_state('bet_0', chat_id)

    def _start(self, chat_id):
        self._sender.send(chat_id, "Welcome!")

    def _help(self, chat_id):
        self._sender.send(chat_id, 'Up-to date coronavirus information: /howmany\nRate: /rate')

    def _howmany(self, chat_id):
        self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date()

        message = f'\nCases (last 24 hours): {cases_day}\nTotal cases: {cases_all}\nLast update: ' \
                  f'{date.isoformat()}'

        self._sender.send(chat_id, message)

    def _rate(self, chat_id):
        message = f"A: заболевших будет <= y\nB: заболевших будет >= (У+1)\n\n"\
                  f"Коэффициент на выигрыш события A: {self._data_keeper.get_rate_A()}\n"\
                  f"Коэффициент на выигрыш события B: {self._data_keeper.get_rate_B()}"

        self._sender.send(chat_id, message)
