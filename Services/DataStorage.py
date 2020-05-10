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
        self.__cursor.execute(f"INSERT INTO users values ('{name}', '{login}', {chat_id}, NULL, NULL, '{lang}')")
        self.__connection.commit()

    def _get_last_bet_id(self, chat_id):
        self.__cursor.execute(f"SELECT ID from bets where user={chat_id}")

        return max(self.__cursor.fetchall(), key=lambda x: x[0])[0]

    def add_bet(self, chat_id, category):
        self._bets_number += 1

        self.__cursor.execute(f"INSERT INTO bets values ({self._bets_number}, '{category}', 0, NULL, {chat_id})")
        self.__connection.commit()

        return self._bets_number  # returns bet id and client save it

    def add_wallet_to_last_bet(self, chat_id, wallet):
        last_bet_id = self._get_last_bet_id(chat_id)
        self.__cursor.execute(f"UPDATE bets SET wallet='{wallet}' WHERE ID={last_bet_id}")
        self.__connection.commit()

    def remove_last_bet(self, chat_id):
        last_bet_id = self._get_last_bet_id(chat_id)
        self.__cursor.execute(f"Delete from bets WHERE ID={last_bet_id}")
        self.__connection.commit()


storage = DataStorage()
print(storage.is_new_user(123))
print(storage.add_user("John Doe", "john_doe", 123, "ru"))
print(storage.is_new_user(123))

storage.add_bet(123, 'A')
storage.add_wallet_to_bet(123, 'abcdef')

storage.add_bet(123, 'B')
storage.add_wallet_to_bet(123, 'abcdef')

storage.remove_last_bet(123)
