import json
import logging
import math
import os
import sqlite3

from Services.Sender import Sender
from Services.Singleton import Singleton
from Services.StatisticsParser import StatisticsParser


# TODO: add self._execute param - list with queries, method opens one connection and
#  execute all queries in one connection
class DataStorage(metaclass=Singleton):
    def __init__(self, settings):
        self._logger = logging.getLogger('Engine.DataStorage')
        self.__database_name = settings['DataStorage']['database_name']

        self._statistics_parser = StatisticsParser(settings)
        self._sender = Sender(settings)

        self._A_wallet = settings['DataStorage']['default_wallet_A'].lower()
        self._B_wallet = settings['DataStorage']['default_wallet_B'].lower()

        self._A_wallet_qr_id = None
        self._B_wallet_qr_id = None

        self._fee = float(settings['DataStorage']['default_fee'])

        self._cases_total = None
        self._cases_day = None
        self._date = None

        self._control_value = None
        self._time_limit = None

        self._bet_amount = float(settings['DataStorage']['default_bet_amount'])

        self.update_statistics()

        if os.path.exists(self.__database_name):
            self._update_rates()
        else:
            self._logger.warning("Database doesn't exist. Creating new one...")

            self._configure_database_first_time()
            self._rate_A, self._rate_B = 'N/a', 'N/a'

        bets_ids = self._execute(['SELECT ID from bets'], method='fetchall')
        transactions_ids = self._execute(['SELECT ID from transactions'], method='fetchall')

        self._last_bet_id = max(bets_ids, key=lambda x: x[0])[0] if bets_ids else 0
        self._last_transaction_id = max(transactions_ids, key=lambda x: x[0])[0] if transactions_ids else 0

        self._logger.info(f'Rates updates. Rate A: {self.rate_A}, Rate B: {self.rate_B}')

        self.basic_keyboard = json.dumps({'keyboard': [
            [{'text': '/how_many'}, {'text': '/bet'}],
            [{'text': '/help'}, {'text': '/status'}]],
            'resize_keyboard': True})

        self._logger.info('DataStorage configured.')

    @property
    def A_wallet_qr_id(self):
        return self._A_wallet_qr_id

    @A_wallet_qr_id.setter
    def A_wallet_qr_id(self, file_id):
        self._A_wallet_qr_id = file_id

    @property
    def B_wallet_qr_id(self):
        return self._B_wallet_qr_id

    @B_wallet_qr_id.setter
    def B_wallet_qr_id(self, file_id):
        self._B_wallet_qr_id = file_id

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

    @bet_amount.setter
    def bet_amount(self, bet_amount):
        self._bet_amount = bet_amount

    @property
    def A_wallet(self):
        return self._A_wallet

    @property
    def B_wallet(self):
        return self._B_wallet

    @A_wallet.setter
    def A_wallet(self, wallet):
        self._A_wallet = wallet
        self._A_wallet_qr_id = None

    @B_wallet.setter
    def B_wallet(self, wallet):
        self._B_wallet = wallet
        self._B_wallet_qr_id = None

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

    def _execute(self, queries_list: list, method=None):
        with sqlite3.connect(self.__database_name) as connection:
            cursor = connection.cursor()

            for query in queries_list:
                try:
                    cursor.execute(query)
                except sqlite3.ProgrammingError as programming_error:
                    self._logger.error(f'Programming error occurred: {programming_error}, QUERY: {query}')
                    self._sender.send_message_to_creator(f'Programming error occurred: {programming_error}, '
                                                         f'QUERY: {query}')

                except sqlite3.OperationalError as operational_error:
                    self._logger.error(f'Operational error occurred: {operational_error}, QUERY: {query}')
                    self._sender.send_message_to_creator(f'Operational error occurred: {operational_error}, '
                                                         f'QUERY: {query}')

                except sqlite3.DatabaseError as database_error:
                    self._logger.error(f'Database error occurred: {database_error}, QUERY: {query}')
                    self._sender.send_message_to_creator(f'Database error occurred: {database_error}, QUERY: {query}')

                except sqlite3.Error as error:
                    self._logger.error(f'Sqlite error occurred: {error}, QUERY: {query}')
                    self._sender.send_message_to_creator(f'Sqlite error occurred: {error}, QUERY: {query}')

            if connection.in_transaction:
                connection.commit()

            if method == 'fetchall':
                return cursor.fetchall()
            elif method == 'fetchone':
                return cursor.fetchone()

    def _update_rates(self):
        bets_A = self.count_confirmed_bets('A')
        bets_B = self.count_confirmed_bets('B')

        self._rate_A = ((bets_A + bets_B) / bets_A) * (1 - self.fee) if bets_A else 'N/a'
        self._rate_B = ((bets_A + bets_B) / bets_B) * (1 - self.fee) if bets_B else 'N/a'

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

        self._execute(['PRAGMA foreign_keys=on',

                       'CREATE TABLE users (name text, login text, '
                       'chat_id integer PRIMARY KEY, state text, wallet text, lang text)',

                       'CREATE TABLE transactions (ID integer PRIMARY KEY, amount float, hash text, from_ text, '
                       'to_ text, is_correct integer)',

                       "INSERT INTO transactions values (0, 0.0, 'default_', 'default_' , 'default_' , 0)",

                       'CREATE TABLE bets (ID integer PRIMARY KEY, category text, confirmed integer, wallet '
                       'text, user integer, transaction_id integer, FOREIGN KEY (user) REFERENCES users(chat_id),'
                       'FOREIGN KEY (transaction_id) REFERENCES transactions(ID))'
                       ])

        self._logger.info('Create table "users".')
        self._logger.info('Create table "transactions" and add default transaction object.')
        self._logger.info('Create table "bets".')

        self._logger.info('Database was successfully configured.')

    def total_eth(self, category):
        wallet = self.A_wallet if category == 'A' else self.B_wallet

        bets = self._execute([f"SELECT amount from transactions WHERE to_='{wallet}'"], method='fetchall')
        return sum([amount[0] for amount in bets])

    def add_transaction(self, amount: float, transaction_hash: str, from_wallet: str, to_wallet: str, is_correct: int):
        self._last_transaction_id += 1

        self._execute([f"INSERT INTO transactions values ({self._last_transaction_id}, {amount}, "
                       f"'{transaction_hash}', '{from_wallet}', '{to_wallet}', {is_correct})"])

        self._logger.info(f'Add new transaction: id - {self._last_transaction_id}, '
                          f'amount - {amount}, from - {from_wallet}, transaction_hash - {transaction_hash}')

        return self._last_transaction_id

    def is_new_transaction(self, transaction_hash: str) -> bool:
        result = self._execute([f"SELECT EXISTS(SELECT ID FROM transactions WHERE hash='{transaction_hash}')"],
                               method='fetchall')

        if not result[0][0]:
            return True

        return False

    def get_users_with_unconfirmed_bets(self) -> set:
        bets_list = self._execute(['SELECT ID,user,category,wallet from bets WHERE confirmed=0'], method='fetchall')

        return set([bet[1] for bet in bets_list])

    def is_new_user(self, chat_id: int) -> bool:
        result = self._execute([f'SELECT EXISTS(SELECT chat_id FROM users WHERE chat_id = {chat_id})'],
                               method='fetchall')

        if not result[0][0]:
            return True

        return False

    def add_user(self, name: str, login, chat_id: int, lang: str):
        login = 'NULL' if not login else login
        self._execute([f"INSERT INTO users values ('{name}', '{login}', {chat_id}, NULL, NULL, '{lang}')"])

        self._logger.info(f'Add new user: name - {name}, login - {login}, chat_id - {chat_id}, lang - {lang}')

    def _get_last_bet_id(self, chat_id: int) -> int:
        bet_id_list = self._execute([f'SELECT ID from bets where user={chat_id} and confirmed=-1'], method='fetchall')

        return max(bet_id_list, key=lambda x: x[0])[0] if bet_id_list else 0

    def add_bet(self, chat_id: int, category: str):
        self._last_bet_id += 1
        self._execute([f"INSERT INTO bets values ({self._last_bet_id}, '{category}', -1, NULL, {chat_id}, 0)"])

        self._logger.info(f'Add new bet: category - {category}, chat_id - {chat_id}')

    def add_wallet_to_last_bet(self, chat_id: int, wallet: str):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self._execute([f"UPDATE bets SET wallet='{wallet}',confirmed=0 WHERE ID={last_bet_id}"])

            self._logger.info(f"Add wallet {wallet} to last user's bet. chat_id: {chat_id}")
        else:
            self._logger.warning(f"Trying to set wallet {wallet} to last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

        self._set_last_wallet(chat_id, wallet)

    def remove_last_bet(self, chat_id: int):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self._execute([f'Delete from bets WHERE ID={last_bet_id}'])

            self._logger.info(f"Remove last user's bet. chat_id: {chat_id}, bet_id: {last_bet_id}")
        else:
            self._logger.warning(f"Trying to remove last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

    def count_confirmed_bets(self, category: str) -> int:
        confirmed_bets_list = self._execute([f"SELECT ID from bets WHERE confirmed=1 AND category='{category}'"],
                                            method='fetchall')

        self._logger.info('Successfully count confirmed bets.')

        return len(confirmed_bets_list)

    def count_unconfirmed_bets(self, category: str) -> int:
        unconfirmed_bets_list = self._execute([f"SELECT ID from bets WHERE confirmed=0 AND category='{category}'"],
                                              method='fetchall')

        self._logger.info('Successfully count confirmed bets.')

        return len(unconfirmed_bets_list)

    def reset_bets(self):
        self._execute(['DELETE FROM bets', 'UPDATE users SET state=NULL'])

        self._rate_A, self._rate_B = 'N/a', 'N/a'
        self._last_bet_id = 0

        self._logger.info('Reset users bets and rates.')

    def get_user_bets(self, chat_id: int) -> list:
        bets_list = self._execute([f'SELECT ID,category,confirmed,wallet from bets WHERE user={chat_id}'
                                   f' AND confirmed!=-1'], method='fetchall')

        return [dict(bet_id=bet[0], category=bet[1], confirmed=bet[2], wallet=bet[3])
                for bet in bets_list]

    def get_users_ids_list(self) -> list:
        return [user_id[0] for user_id in self._execute(['SELECT chat_id from users'], method='fetchall')]

    def get_unconfirmed_bets(self, chat_id: int) -> list:
        bets_list = self._execute([f'SELECT ID,user,category,wallet from bets WHERE confirmed=0 and user={chat_id}'],
                                  method='fetchall')

        return [dict(bet_id=bet[0], chat_id=bet[1], wallet=bet[3], category=bet[2])
                for bet in bets_list]

    def get_unconfirmed_bets_all(self) -> list:
        bets_list = self._execute(['SELECT ID,user,category,wallet from bets WHERE confirmed=0'], method='fetchall')

        return [dict(bet_id=bet[0], chat_id=bet[1], wallet=bet[3], category=bet[2])
                for bet in bets_list]

    def confirm_bet(self, bet_id: int, transaction_id: int):
        self._execute([f'UPDATE bets SET confirmed=1,transaction_id = {transaction_id} WHERE ID={bet_id}'])

        self._logger.info(f'Bet confirmed, bet_id: {bet_id}')
        self._update_rates()

    def get_last_bet_category(self, chat_id: int):
        bets_list = self._execute([f'SELECT ID,category from bets where user={chat_id} and confirmed=-1'],
                                  method='fetchall')

        return max(bets_list, key=lambda x: x[0])[1] if bets_list else None

    def get_user_state(self, chat_id: int):
        user_state = self._execute([f'SELECT state from users WHERE chat_id={chat_id}'], method='fetchone')
        return None if user_state and user_state[0] == 'NULL' else user_state[0]

    def set_user_state(self, new_state: str, chat_id: int):
        if not new_state:
            self._execute([f'UPDATE users SET state=NULL WHERE chat_id={chat_id}'])
        else:
            self._execute([f"UPDATE users SET state='{new_state}' WHERE chat_id={chat_id}"])

        self._logger.info(f'Set user state. chat_id: {chat_id}, state: {new_state}')

    def _set_last_wallet(self, chat_id: int, wallet: str):
        self._execute([f"UPDATE users SET wallet='{wallet}' WHERE chat_id={chat_id}"])

        self._logger.info(f'Set last wallet. chat_id" {chat_id}, wallet: {wallet}')

    def get_last_wallet(self, chat_id: int) -> str:
        wallet = self._execute([f'SELECT wallet from users WHERE chat_id={chat_id}'], method='fetchone')[0]

        return None if wallet == 'NULL' else wallet
