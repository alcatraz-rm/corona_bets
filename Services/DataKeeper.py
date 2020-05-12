import json
import logging


from Services.Singleton import Singleton
from Services.EventParser import EventParser


class DataKeeper(metaclass=Singleton):
    def __init__(self):
        self._logger = logging.getLogger('Engine.DataKeeper')

        self._event_parser = EventParser()

        self._event_A_wallet = '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        self._event_B_wallet = '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'

        self._users = self._read_users()

        self._rate_A = 'N/a'
        self._rate_B = 'N/a'
        self._fee = 0.1

        self._cases_all = None
        self._cases_day = None
        self._date = None

        self._control_value = 123
        self._time_limit = 'time limit here'

        self._bet_amount = 0.03

        self.responses = self._read_responses()

        self.update()
        self._logger.info('DataKeeper initialized.')

    @staticmethod
    def _read_responses():
        with open("responses.json", 'r', encoding='utf-8') as responses_file:
            return json.load(responses_file)

    def get_bet_amount(self):
        return self._bet_amount

    def set_bet_amount(self, bet_amount):
        self._bet_amount = bet_amount

    def get_time_limit(self):
        return self._time_limit

    def set_time_limit(self, new_time_limit):
        self._time_limit = new_time_limit

    def get_control_value(self):
        return self._control_value

    def remove_last_bet(self, chat_id):
        for n in range(len(self._users)):
            if self._users[n]['chat_id'] == chat_id:
                del(self._users[n]['bets'][-1])
                self._commit()

                return

    def get_lang(self, chat_id):
        for user in self._users:
            if user['chat_id'] == chat_id:
                return user['lang']

    def get_bets(self, chat_id):
        for user in self._users:
            if user['chat_id'] == chat_id:
                return user['bets']

    def get_users(self, category):
        if category:
            result = []

            for user in self._users:
                if user['category'] == category:
                    result.append(user)

            return result
        else:
            return self._users

    def count_bets(self, category):
        result = 0

        for user in self._users:
            for bet in user['bets']:
                if bet['category'] == category:
                    result += 1

        return result

    def reset_users(self):
        for n in range(len(self._users)):
            self._users[n]['state'] = None
            self._users[n]['bets'] = []

        self._commit()

        self._rate_A, self._rate_B = 'N/a', 'N/a'
        self._logger.info('Users and rates were reset.')

    def get_unverified_bets(self):
        pass

    def update(self):
        data = self._event_parser.update()

        self._cases_all = data['total']
        self._cases_day = data['day']
        self._date = data['date']

        self._logger.info('Event updated.')

    def is_new_user(self, message):
        chat_id = message['message']['from']['id']

        for user in self._users:
            if user['chat_id'] == chat_id:
                return False

        return True

    def get_state(self, chat_id):
        for index, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                return user['state']

    def set_state(self, new_state, chat_id):
        for index, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[index]['state'] = new_state
                self._commit()
                return

    def set_wallet(self, new_wallet_id, chat_id):
        for index, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[index]['wallet'] = new_wallet_id
                self._commit()
                return

    def add_user(self, message):
        if 'last_name' in message['message']['from']:
            name = f"{message['message']['from']['first_name']} {message['message']['from']['last_name']}"
        else:
            name = f"{message['message']['from']['first_name']}"

        if 'username' in message['message']['from']:
            login = message['message']['from']['username']
        else:
            login = None

        chat_id = message['message']['from']['id']

        self._users.append({'name': name, 'login': login, 'chat_id': chat_id, 'state': None, 'wallet': None,
                            'bets': [], 'lang': 'ru'})

        self._commit()
        self._logger.info(f'Add new user: {name}, {chat_id}')

    def add_bet(self, chat_id, category):
        for n, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[n]['bets'].append({'category': category,
                                               'confirmed': False,
                                               'wallet': None,
                                               })
                self._commit()
                return

    def _commit(self):
        with open("users.json", "w", encoding="utf-8") as users_file:
            json.dump(self._users, users_file, indent=4, ensure_ascii=False)

    def add_wallet_to_last_bet(self, chat_id, wallet):
        for n, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[n]['bets'][-1]['wallet'] = wallet
                self._commit()
                return

    @staticmethod
    def _read_users():
        with open("users.json", "r", encoding="utf-8") as users_file:
            return json.load(users_file)

    def get_cases_day(self):
        return self._cases_day

    def set_control_value(self, control_value):
        self._control_value = control_value

    def get_cases_all(self):
        return self._cases_all

    def get_date(self):
        return self._date

    def get_rate_A(self):
        return self._rate_A

    def get_rate_B(self):
        return self._rate_B

    def get_A_wallet(self):
        return self._event_A_wallet

    def get_B_wallet(self):
        return self._event_B_wallet

    def get_fee(self):
        return self._fee

    def set_fee(self, fee):
        self._fee = fee

    def get_wallet(self, chat_id):
        for user in self._users:
            if user['chat_id'] == chat_id:
                return user['wallet']

    def update_rates(self, rate_A, rate_B):
        self._rate_A, self._rate_B = rate_A, rate_B
        self._logger.info('Rates updated.')

    def set_lang(self, chat_id, lang):
        for n, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[n]['lang'] = lang
                break

        self._commit()
