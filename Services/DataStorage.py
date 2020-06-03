import json
import logging
import math
import os
import sqlite3

from Services.Singleton import Singleton
from Services.StatisticsParser import StatisticsParser


class DataStorage(metaclass=Singleton):
    def __init__(self, settings):
        self._logger = logging.getLogger('Engine.DataStorage')
        self.__database_name = settings['DataStorage']['database_name']

        self._statistics_parser = StatisticsParser(settings)

        self._A_wallet = '0x34BC5AB1f9ABFA02C3A22354Bf1e11f7EA6614a1'.lower()
        self._B_wallet = '0x7fa03c381D62DB37BcCb29e2Dab48d6D53c8a3d8'.lower()
        self._fee = float(settings['DataStorage']['default_fee'])

        self._cases_total = None
        self._cases_day = None
        self._date = None

        self._control_value = 123
        self._time_limit = 'time limit here'

        self._bet_amount = float(settings['DataStorage']['default_bet_amount'])

        self.update_statistics()

        if os.path.exists(self.__database_name):
            self._update_rates()
        else:
            self._logger.warning("Database doesn't exist. Creating new one...")

            connection = sqlite3.connect(self.__database_name)
            connection.close()

            self._logger.info('Create database.')

            self._configure_database_first_time()
            self._rate_A = 'N/a'
            self._rate_B = 'N/a'

        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT ID from bets')
            bets_ids = cursor.fetchall()

            if bets_ids:
                self._last_bet_id = max(bets_ids, key=lambda x: x[0])[0]
            else:
                self._last_bet_id = 0

            cursor.execute('SELECT ID from transactions')
            transactions_ids = cursor.fetchall()

            if transactions_ids:
                self._last_transaction_id = max(transactions_ids, key=lambda x: x[0])[0]
            else:
                self._last_transaction_id = 0

            self._logger.info(f'Rates updates. Rate A: {self.rate_A}, Rate B: {self.rate_B}')

        self.basic_keyboard = json.dumps({'keyboard': [
            [{'text': '/how_many'}, {'text': '/bet'}],
            [{'text': '/help'}, {'text': '/status'}]],
            'resize_keyboard': True})

        self._logger.info('DataStorage configured.')

    @property
    def fee(self):
        return self._fee

    @property
    def represented_rates(self):
        return self._represent_rates(self._rate_A, self._rate_B)

    @fee.setter
    def fee(self, fee):
        self._fee = fee
        self._update_rates()

    @property
    def rate_A(self):
        return self._rate_A

    @property
    def rate_B(self):
        return self._rate_B

    @property
    def bet_amount(self):
        return self._bet_amount

    @property
    def A_wallet(self):
        return self._A_wallet

    @property
    def B_wallet(self):
        return self._B_wallet

    @A_wallet.setter
    def A_wallet(self, wallet):
        self._A_wallet = wallet

    @B_wallet.setter
    def B_wallet(self, wallet):
        self._B_wallet = wallet

    @property
    def cases_day(self):
        return self._cases_day

    @property
    def cases_total(self):
        return self._cases_total

    @property
    def date(self):
        return self._date

    @property
    def control_value(self):
        return self._control_value

    @control_value.setter
    def control_value(self, new_control_value):
        self._control_value = new_control_value

    @property
    def time_limit(self):
        return self._time_limit

    @time_limit.setter
    def time_limit(self, new_time_limit):
        self._time_limit = new_time_limit

    def _update_rates(self):
        bets_A = self.count_confirmed_bets('A')
        bets_B = self.count_confirmed_bets('B')

        if bets_A:
            self._rate_A = ((bets_A + bets_B) / bets_A) * (1 - self.fee)
        else:
            self._rate_A = 'N/a'

        if bets_B:
            self._rate_B = ((bets_A + bets_B) / bets_B) * (1 - self.fee)
        else:
            self._rate_B = 'N/a'

    @staticmethod
    def _represent_rates(rate_A, rate_B) -> (str, str):
        if rate_A != 'N/a' and rate_B != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(math.trunc(rate_B * 1000) / 1000)

        elif rate_A != 'N/a':
            return str(math.trunc(rate_A * 1000) / 1000), str(rate_B)

        elif rate_B != 'N/a':
            return str(math.trunc(rate_B * 1000) / 1000), str(rate_A)

        else:
            return str(rate_A), str(rate_B)

    def update_statistics(self):
        statistics = self._statistics_parser.update()

        self._cases_total = statistics['total']
        self._cases_day = statistics['day']
        self._date = statistics['date']

        self._logger.info('Statistics updated.')

    def _configure_database_first_time(self):
        self._logger.info('Start configuring database.')

        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=on')

            cursor.execute('CREATE TABLE users (name text, login text, chat_id integer PRIMARY KEY, '
                           'state text, wallet text, lang text)')

            self._logger.info('Create table "users".')

            cursor.execute('CREATE TABLE transactions (ID integer PRIMARY KEY, amount float, hash text, from_ text, '
                           'to_ text, is_correct integer)')

            cursor.execute("INSERT INTO transactions values (0, 0.0, 'default_', 'default_' , 'default_' , 0)")

            self._logger.info('Create table "transactions" and add default transaction object.')

            cursor.execute('CREATE TABLE bets (ID integer PRIMARY KEY, category text, confirmed integer, wallet '
                           'text, user integer, transaction_id integer, FOREIGN KEY (user) REFERENCES users(chat_id),'
                           'FOREIGN KEY (transaction_id) REFERENCES transactions(ID))')

            self._logger.info('Create table "bets".')

        self._logger.info('Database was successfully configured.')

    def total_eth(self, category):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            wallet = self.B_wallet
            if category == 'A':
                wallet = self.A_wallet

            cursor.execute(f"SELECT amount from transactions WHERE to_='{wallet}'")
            transactions_sums = [amount[0] for amount in cursor.fetchall()]

        return sum(transactions_sums)

    def add_transaction(self, amount: float, transaction_hash: str, from_wallet: str, to_wallet: str, is_correct: int):
        self._last_transaction_id += 1

        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"INSERT INTO transactions values ({self._last_transaction_id}, {amount}, "
                           f"'{transaction_hash}', '{from_wallet}', '{to_wallet}', {is_correct})")

        self._logger.info(f'Add new transaction: id - {self._last_transaction_id}, '
                          f'amount - {amount}, from - {from_wallet}, transaction_hash - {transaction_hash}')

        return self._last_transaction_id

    def is_new_transaction(self, transaction_hash: str) -> bool:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT EXISTS(SELECT ID FROM transactions WHERE hash='{transaction_hash}')")
            result = cursor.fetchall()

        if not result[0][0]:
            return True

        return False

    def get_users_with_unconfirmed_bets(self) -> list:
        result = []

        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT ID,user,category,wallet from bets WHERE confirmed=0')

        bets_list = [dict(bet_id=bet[0], chat_id=bet[1], wallet=bet[3], category=bet[2])
                     for bet in cursor.fetchall()]

        for bet in bets_list:
            if not bet['chat_id'] in result:
                result.append(bet['chat_id'])

        return result

    def is_new_user(self, chat_id: int) -> bool:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'SELECT EXISTS(SELECT chat_id FROM users WHERE chat_id = {chat_id})')
            result = cursor.fetchall()

        if not result[0][0]:
            return True

        return False

    def add_user(self, name: str, login, chat_id: int, lang: str):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            if login:
                cursor.execute(f"INSERT INTO users values ('{name}', '{login}', {chat_id}, NULL, NULL, '{lang}')")
            else:
                cursor.execute(f"INSERT INTO users values ('{name}', NULL, {chat_id}, NULL, NULL, '{lang}')")

            connection.commit()

        self._logger.info(f'Add new user: name - {name}, login - {login}, chat_id - {chat_id}, lang - {lang}')

    def _get_last_bet_id(self, chat_id: int) -> int:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            cursor.execute(f'SELECT ID from bets where user={chat_id} and confirmed=-1')
            bet_id_list = cursor.fetchall()

            if bet_id_list:
                return max(bet_id_list, key=lambda x: x[0])[0]
            else:
                return 0

    def add_bet(self, chat_id: int, category: str):
        self._last_bet_id += 1

        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"INSERT INTO bets values ({self._last_bet_id}, '{category}', -1, NULL, {chat_id}, 0)")
            connection.commit()

        self._logger.info(f'Add new bet: category - {category}, chat_id - {chat_id}')

    def add_wallet_to_last_bet(self, chat_id: int, wallet: str):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            with sqlite3.connect(self.__database_name) as connection:
                cursor = connection.cursor()
                cursor.execute(f"UPDATE bets SET wallet='{wallet}',confirmed=0 WHERE ID={last_bet_id}")
                connection.commit()

            self._logger.info(f"Add wallet {wallet} to last user's bet. chat_id: {chat_id}")
        else:
            self._logger.warning(f"Trying to set wallet {wallet} to last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

        self._set_last_wallet(chat_id, wallet)

    def remove_last_bet(self, chat_id: int):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            with sqlite3.connect(self.__database_name) as connection:
                cursor = connection.cursor()
                cursor.execute(f'Delete from bets WHERE ID={last_bet_id}')
                connection.commit()

            self._logger.info(f"Remove last user's bet. chat_id: {chat_id}, bet_id: {last_bet_id}")
        else:
            self._logger.warning(f"Trying to remove last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

    def count_confirmed_bets(self, category: str) -> int:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT ID from bets WHERE confirmed=1 AND category='{category}'")

            self._logger.info('Successfully count confirmed bets.')

            return len(cursor.fetchall())

    def count_unconfirmed_bets(self, category: str) -> int:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT ID from bets WHERE confirmed=0 AND category='{category}'")

            self._logger.info('Successfully count confirmed bets.')

            return len(cursor.fetchall())

    def reset_bets(self):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            cursor.execute('DELETE FROM bets')
            cursor.execute('UPDATE users SET state=NULL')
            connection.commit()

        self._rate_A, self._rate_B = 'N/a', 'N/a'
        self._last_bet_id = 0

        self._logger.info('Reset users bets and rates.')

    def get_user_bets(self, chat_id: int) -> list:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'SELECT ID,category,confirmed,wallet from bets WHERE user={chat_id}'
                           f' AND confirmed!=-1')

            return [dict(bet_id=bet[0], category=bet[1], confirmed=bet[2], wallet=bet[3])
                    for bet in cursor.fetchall()]

    def get_users_ids_list(self) -> list:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT chat_id from users')

            return [user_id[0] for user_id in cursor.fetchall()]

    def get_unconfirmed_bets(self, chat_id: int) -> list:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'SELECT ID,user,category,wallet from bets WHERE confirmed=0 and user={chat_id}')

            return [dict(bet_id=bet[0], chat_id=bet[1], wallet=bet[3], category=bet[2])
                    for bet in cursor.fetchall()]

    def get_unconfirmed_bets_all(self) -> list:
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT ID,user,category,wallet from bets WHERE confirmed=0')

            return [dict(bet_id=bet[0], chat_id=bet[1], wallet=bet[3], category=bet[2])
                    for bet in cursor.fetchall()]

    def confirm_bet(self, bet_id: int, transaction_id: int):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'UPDATE bets SET confirmed=1,transaction_id = {transaction_id} WHERE ID={bet_id}')
            connection.commit()

        self._logger.info(f'Bet confirmed, bet_id: {bet_id}')
        self._update_rates()

    def get_last_bet_category(self, chat_id: int):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            cursor.execute(f'SELECT ID,category from bets where user={chat_id} and confirmed=-1')
            bets_list = cursor.fetchall()

            if bets_list:
                return max(bets_list, key=lambda x: x[0])[1]
            else:
                return None

    def get_user_state(self, chat_id: int):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'SELECT state from users WHERE chat_id={chat_id}')
            user_state = cursor.fetchone()

            if user_state:
                if user_state[0] == 'NULL':
                    return None

                return user_state[0]

    def set_user_state(self, new_state: str, chat_id: int):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            if not new_state:
                cursor.execute(f'UPDATE users SET state=NULL WHERE chat_id={chat_id}')
            else:
                cursor.execute(f"UPDATE users SET state='{new_state}' WHERE chat_id={chat_id}")

            connection.commit()

            self._logger.info(f'Set user state. chat_id: {chat_id}, state: {new_state}')

    def _set_last_wallet(self, chat_id: int, wallet: str):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"UPDATE users SET wallet='{wallet}' WHERE chat_id={chat_id}")

            connection.commit()

        self._logger.info(f'Set last wallet. chat_id" {chat_id}, wallet: {wallet}')

    def get_last_wallet(self, chat_id: int):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f'SELECT wallet from users WHERE chat_id={chat_id}')

            wallet = cursor.fetchone()[0]

        if wallet == 'NULL':
            wallet = None

        return wallet
