import sqlite3
import os
import logging

from Services.Singleton import Singleton


class DataStorage(metaclass=Singleton):
    def __init__(self):
        self._logger = logging.getLogger('Engine.DataStorage')

        if not os.path.exists('user_data.db'):
            self._logger.warning("Database doesn't exist. Creating new one...")

            self.__connection = sqlite3.connect('user_data.db')
            self.__cursor = self.__connection.cursor()

            self._logger.info("Create database and get cursor.")

            self._configure_database_first_time()
        else:
            self.__connection = sqlite3.connect('user_data.db')
            self.__cursor = self.__connection.cursor()

        self.__cursor.execute("SELECT * from bets")
        self._bets_number = len(self.__cursor.fetchall())

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
        self._bets_number += 1

        self.__cursor.execute(f"INSERT INTO bets values ({self._bets_number}, '{category}', 0, NULL, {chat_id})")
        self.__connection.commit()

        self._logger.info(f"Add new bet: category - {category}, chat_id - {chat_id}")

    def add_wallet_to_last_bet(self, chat_id, wallet):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self.__cursor.execute(f"UPDATE bets SET wallet='{wallet}' WHERE ID={last_bet_id}")
            self.__connection.commit()

            self._logger.info(f"Add wallet {wallet} to last user's bet. chat_id: {chat_id}")
        else:
            self._logger.warning(f"Trying to set wallet {wallet} to last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")

    def remove_last_bet(self, chat_id):
        last_bet_id = self._get_last_bet_id(chat_id)

        if last_bet_id:
            self.__cursor.execute(f"Delete from bets WHERE ID={last_bet_id}")
            self.__connection.commit()

            self._logger.info(f"Remove last user's bet. chat_id: {chat_id}, bet_id: {last_bet_id}")
        else:
            self._logger.warning(f"Trying to remove last user's bet, but this user doesn't have bets."
                                 f"chat_id: {chat_id}")


storage = DataStorage()
print(storage.is_new_user(123))
print(storage.add_user("John Doe", "john_doe", 123, "ru"))
print(storage.is_new_user(123))

storage.remove_last_bet(123)
