import sqlite3
import os
import logging
import json

from Services.Singleton import Singleton
from Services.EventParser import EventParser


class DataStorage(metaclass=Singleton):
    def __init__(self):
        self._logger = logging.getLogger('Engine.DataStorage')
        self._event_parser = EventParser()

        self.A_wallet = '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        self.B_wallet = '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
        self.fee = 0.1

        self.cases_total = None
        self.cases_day = None
        self.date = None

        self.control_value = 123
        self.time_limit = 'time limit here'

        self.bet_amount = 0.03

        # self.responses = self._read_responses()

        self.update_statistics()

        if not os.path.exists('user_data.db'):
            self._logger.warning("Database doesn't exist. Creating new one...")

            self.__connection = sqlite3.connect('user_data.db')
            self.__cursor = self.__connection.cursor()

            self._logger.info("Create database and get cursor.")

            self._configure_database_first_time()
            self.rate_A = 'N/a'
            self.rate_B = 'N/a'
        else:
            self.__connection = sqlite3.connect('user_data.db')
            self.__cursor = self.__connection.cursor()

            self._update_rates()

        self.__cursor.execute("SELECT * from bets")
        self._last_bet_id = len(self.__cursor.fetchall())

    @staticmethod
    def _read_responses():
        with open("responses.json", 'r', encoding='utf-8') as responses_file:
            return json.load(responses_file)

    def _update_rates(self):
        bets_A = self.count_confirmed_bets('A')
        bets_B = self.count_confirmed_bets('B')

        if bets_A:
            self.rate_A = ((bets_A + bets_B) / bets_A) * (1 - self.fee)
        else:
            self.rate_A = 'N/a'

        if bets_B:
            self.rate_B = ((bets_A + bets_B) / bets_B) * (1 - self.fee)
        else:
            self.rate_B = 'N/a'

    def update_statistics(self):
        data = self._event_parser.update()

        self.cases_total = data['total']
        self.cases_day = data['day']
        self.date = data['date']

        self._logger.info('Statistics updated.')

    def _configure_database_first_time(self):
        self._logger.info('Start configuring database.')
        self.__cursor.execute("PRAGMA foreign_keys=on")

        self.__cursor.execute("CREATE TABLE users (name text, login text, chat_id integer PRIMARY KEY, "
                              "state text, wallet text, lang text)")

        self._logger.info("Create table 'users'.")

        self.__cursor.execute("CREATE TABLE bets (ID integer PRIMARY KEY, category text, confirmed integer, wallet "
                              "text, user integer, FOREIGN KEY (user) REFERENCES users(chat_id))")

        self._logger.info("Create table 'bets'")
        self._logger.info('Database was successfully configured.')

    def is_new_user(self, chat_id):
        self.__cursor.execute(f"SELECT EXISTS(SELECT chat_id FROM users WHERE chat_id = {chat_id})")
        result = self.__cursor.fetchall()
        print(result)

        if result[0][0]:
            return True

        return False

    def add_user(self, name, login, chat_id, lang):
        if login:
            self.__cursor.execute(f"INSERT INTO users values ('{name}', '{login}', {chat_id}, NULL, NULL, '{lang}')")
        else:
            self.__cursor.execute(f"INSERT INTO users values ('{name}', NULL, {chat_id}, NULL, NULL, '{lang}')")

        self.__connection.commit()

        self._logger.info(f"Add new user: name - {name}, login - {login}, chat_id - {chat_id}, lang - {lang}")

    def _get_last_bet_id(self, chat_id):
        self.__cursor.execute(f"SELECT ID from bets where user={chat_id}")
        bets_ids = self.__cursor.fetchall()

        if bets_ids:
            return max(self.__cursor.fetchall(), key=lambda x: x[0])[0]
        else:
            return None

    def add_bet(self, chat_id, category):
        self._last_bet_id += 1

        self.__cursor.execute(f"INSERT INTO bets values ({self._last_bet_id}, '{category}', -1, NULL, {chat_id})")
        self.__connection.commit()

        self._logger.info(f"Add new bet: category - {category}, chat_id - {chat_id}")

    def add_wallet_to_last_bet(self, chat_id, wallet):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self.__cursor.execute(f"UPDATE bets SET wallet='{wallet}' SET confirmed=0 WHERE ID={last_bet_id}")
            self.__connection.commit()

            self._logger.info(f"Add wallet {wallet} to last user's bet. chat_id: {chat_id}")
        else:
            self._logger.warning(f"Trying to set wallet {wallet} to last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

        self._set_last_wallet(chat_id, wallet)

    def remove_last_bet(self, chat_id):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self.__cursor.execute(f"Delete from bets WHERE ID={last_bet_id}")
            self.__connection.commit()

            self._logger.info(f"Remove last user's bet. chat_id: {chat_id}, bet_id: {last_bet_id}")
        else:
            self._logger.warning(f"Trying to remove last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

    def count_confirmed_bets(self, category):
        self.__cursor.execute(f"SELECT ID from bets WHERE confirmed=1 AND category='{category}'")
        return len(self.__cursor.fetchall())

    def reset_users_bets(self):
        self.__cursor.execute("TRUNCATE TABLE bets")
        self.__cursor.execute("UPDATE users SET state=NULL")

        self.rate_A, self.rate_B = 'N/a', 'N/a'

        self.__connection.commit()

    def get_bets(self, chat_id):
        self.__cursor.execute(f"SELECT ID,category,confirmed,wallet from bets WHERE user={chat_id}"
                              f" AND confirmed=0 OR confirmed=1")

        return [dict(bet_id=bet[0], category=bet[1], confirmed=bet[2], wallet=bet[3])
                for bet in self.__cursor.fetchall()]

    def get_users_ids(self):
        self.__cursor.execute(f"SELECT chat_id from users")
        return [user_id[0] for user_id in self.__cursor.fetchall()]

    def get_unconfirmed_bets(self):
        self.__cursor.execute("SELECT ID,category,confirmed,wallet,user from bets WHERE confirmed=0")
        return [dict(bet_id=bet[0], category=bet[1], confirmed=bet[2], wallet=bet[3], user=bet[4])
                for bet in self.__cursor.fetchall()]

    def confirm_bet(self, bet_id):
        self.__cursor.execute(f"UPDATE bets SET confirmed=1 WHERE ID={bet_id}")
        self.__connection.commit()

        self._update_rates()

    def get_state(self, chat_id):
        self.__cursor.execute(f"SELECT state from users WHERE chat_id={chat_id}")
        state = self.__cursor.fetchone()[0]

        if state == 'NULL':
            return None

        return state

    def set_state(self, state, chat_id):
        if not state:
            state = 'NULL'

        self.__cursor.execute(f"UPDATE bets SET state={state} WHERE chat_id={chat_id}")
        self.__connection.commit()

    def _set_last_wallet(self, chat_id, wallet):
        self.__cursor.execute(f"UPDATE users SET wallet='{wallet}' WHERE chat_id={chat_id}")
        self.__connection.commit()

    def get_last_wallet(self, chat_id):
        self.__cursor.execute(f"SELECT wallet from bets WHERE user={chat_id}")
        wallet = self.__cursor.fetchone()[0]

        if wallet == 'NULL':
            return None

        return wallet


storage = DataStorage()
print(storage.get_last_wallet(123))

