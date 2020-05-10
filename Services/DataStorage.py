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

    def _configure_database_first_time(self):
        self._logger.info('Start configuring database.')
        self.__cursor.execute("PRAGMA foreign_keys=on")

        self.__cursor.execute("CREATE TABLE users (name text, login text, chat_id integer PRIMARY KEY, "
                              "state text, wallet text, lang text)")

        self._logger.info("Create table 'users'.")

        self.__cursor.execute("CREATE TABLE bets (category text, status text, wallet text, user integer PRIMARY KEY, "
                              "FOREIGN KEY (user) REFERENCES users(chat_id))")

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
        self.__cursor.execute(f"INSERT INTO users values ('{name}', '{login}', {chat_id}, 'null', 'null', '{lang}')")
        self.__connection.commit()


storage = DataStorage()
print(storage.is_new_user(123))
print(storage.add_user("John Doe", "john_doe", 123, "ru"))
print(storage.is_new_user(123))

