import json

from Services.Singleton import Singleton
from Services.EventParser import EventParser


class DataKeeper(metaclass=Singleton):
    def __init__(self):
        self._event_parser = EventParser()

        self._event_A = 'Заболевших будет <= y'
        self._event_B = 'Заболевших будет > y'

        self._event_A_wallet = 'here must be A wallet id'
        self._event_B_wallet = 'here must be B wallet id'

        self._users = self._read_users()

        self._rate_A = 0
        self._rate_B = 0
        self._fee = 0.1

        self._cases_all = None
        self._cases_day = None
        self._date = None

        self.responses = self._read_responses()

        self.update()

    @staticmethod
    def _read_responses():
        with open("responses.json", 'r', encoding='utf-8') as responses_file:
            return json.load(responses_file)

    def get_lang(self, chat_id):
        for user in self._users:
            if user['chat_id'] == chat_id:
                return user['lang']

    def get_users(self, category):
        result = []

        for user in self._users:
            if user['category'] == category:
                result.append(user)

        return result

    def reset_users(self):
        for n in range(len(self._users)):
            self._users[n]['state'] = None
            self._users[n]['category'] = None
            self._users[n]['vote_verified'] = False

        self._commit()

    def update(self):
        data = self._event_parser.update()

        self._cases_all = data['total']
        self._cases_day = data['day']
        self._date = data['date']

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

    def set_category(self, chat_id, category):
        for index, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[index]['category'] = category
                self._commit()
                return

    def set_wallet(self, new_wallet_id, chat_id):
        for index, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[index]['wallet'] = new_wallet_id
                self._commit()
                return

    def add_user(self, message):
        name = f"{message['message']['from']['first_name']} {message['message']['from']['last_name']}"
        login = message['message']['from']['username']
        chat_id = message['message']['from']['id']

        self._users.append({'name': name, 'login': login, 'chat_id': chat_id, 'state': None, 'wallet': None,
                            'category': None, 'vote_verified': False, 'lang': 'ru'})

        self._commit()

    def _commit(self):
        with open("users.json", "w", encoding="utf-8") as users_file:
            json.dump(self._users, users_file, indent=4)

    @staticmethod
    def _read_users():
        with open("users.json", "r", encoding="utf-8") as users_file:
            return json.load(users_file)

    def get_cases_day(self):
        return self._cases_day

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

    def get_wallet(self, chat_id):
        for user in self._users:
            if user['chat_id'] == chat_id:
                return user['wallet']

    def update_rates(self, rate_A, rate_B):
        self._rate_A, self._rate_B = rate_A, rate_B

    def set_lang(self, chat_id, lang):
        for n, user in enumerate(self._users):
            if user['chat_id'] == chat_id:
                self._users[n]['lang'] = lang
                break

        self._commit()
