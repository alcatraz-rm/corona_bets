from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.Sender import Sender

from datetime import datetime, timedelta
from jinja2 import FileSystemLoader, Environment
from threading import Lock


class Admin:
    def __init__(self, telegram_access_token, etherscan_api_token):
        self._admin_chat_id = None  # get it from environment variable
        self._admin_pin_code = None

        self._sender = Sender(telegram_access_token)
        self._ether_scan = EtherScan(telegram_access_token, etherscan_api_token)
        self._data_storage = DataStorage()
        self._templates_env = Environment(loader=FileSystemLoader('admin_responses'))

        self._admin_sessions_list = []
        self._auth_queries = []
        self._max_auth_tries = 5

        self._commands = ['/set_wallet', '/set_fee', '/set_vote_end_time', '/admin_cancel',
                          '/stat', '/pay_out']

    def _has_active_session(self, chat_id):
        for n, session in enumerate(self._admin_sessions_list):
            if session['chat_id'] == chat_id:
                if session['login_time'] - datetime.utcnow() >= timedelta(minutes=30):
                    del(self._admin_sessions_list[n])
                    return False

                return True

        return False

    def is_authorize_query(self, message):
        chat_id = message['message']['from']['id']

        return not self._find_auth_query_index(chat_id) == -1

    def _check_auth_info(self):
        valid_auth_queries = []
        valid_sessions = []

        for n, auth_query in enumerate(self._auth_queries):
            if auth_query['creation_time'] - datetime.utcnow() < timedelta(minutes=5):
                valid_auth_queries.append(self._auth_queries[n])

        self._auth_queries = valid_auth_queries

        for n, session in self._admin_sessions_list:
            if session['login_time'] - datetime.utcnow() < timedelta(minutes=30):
                valid_sessions.append(self._admin_sessions_list[n])

        self._admin_sessions_list = valid_sessions

    def handle_command(self, command):
        self._check_auth_info()

        chat_id = command['message']['from']['id']

        if command['message']['chat']['id'] != self._admin_chat_id:
            self._sender.send_message(chat_id, self._templates_env.get_template('default_answer_text.jinja').render(),
                                      reply_markup=self._data_storage.basic_keyboard)
            return

        if not self._has_active_session(chat_id):
            self._auth_queries.append({'chat_id': chat_id, 'tries': self._max_auth_tries,
                                       'creation_time': datetime.utcnow()})

            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('authorize_message_chat.jinja'))
            self._sender.send_message(chat_id, self._templates_env.get_template('authorize_message_personally.jinja'))
            return

        else:
            text = command['message']['text'].split()
            command_type = text[0]
            args = text[1:]

            if command_type == '/set_wallet':
                self._set_wallet(chat_id, args)
            elif command_type == '/set_fee':
                self._set_fee(chat_id, args)
            elif command_type == '/set_vote_end_time':
                pass
            elif command_type == '/stat':
                pass
            elif command_type == '/pay_out':
                pass
            elif command_type == 'admin_cancel':
                pass

    # TODO: datetime.now(timezone.utc)
    def _set_vote_end_time(self, chat_id, args):
        hour = int(args[0])

        if hour < 1 or hour > 23:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_time.jinja').render())
            return

        new_time_limit = self._data_storage.time_limit
        new_time_limit.hour = hour

        if datetime.utcnow() > new_time_limit:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_time.jinja').render())
            return

        self._data_storage.time_limit.hour = hour

        self._sender.send_message(chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _set_fee(self, chat_id, args):
        try:
            fee = int(args[0])
        except ValueError:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_fee.jinja').render())
            return

        if fee <= 0 or fee >= 100:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_fee.jinja').render())
            return

        self._data_storage.fee = fee / 100

        self._sender.send_message(chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _set_wallet(self, chat_id, args):
        category = args[0]
        wallet = args[1]

        if category not in ['A', 'B']:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_category.jinja').render())
            return

        if not self._ether_scan.wallet_is_correct(wallet):
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_wallet.jinja').render())
            return

        if category == 'A':
            self._data_storage.A_wallet = wallet
        else:
            self._data_storage.B_wallet = wallet
        self._sender.send_message(chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _find_auth_query_index(self, chat_id):
        for n, auth_query in enumerate(self._auth_queries):
            if auth_query['chat_id'] == chat_id:
                return n

        return -1

    def auth(self, message):
        chat_id = message['message']['from']['chat_id']
        auth_query_index = self._find_auth_query_index(chat_id)

        if message['message']['text'] == self._admin_pin_code:
            del(self._auth_queries[auth_query_index])
            self._admin_sessions_list.append({'chat_id': chat_id, 'login_time': datetime.utcnow()})

        else:
            self._auth_queries[auth_query_index]['tries'] -= 1

            if self._auth_queries[auth_query_index]['tries'] == 0:
                del(self._auth_queries[auth_query_index])
                # send message about that
