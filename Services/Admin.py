import math
from datetime import datetime, timedelta

from jinja2 import FileSystemLoader, Environment

from Services.DataStorage import DataStorage
from Services.EtherScan import EtherScan
from Services.Sender import Sender


class Admin:
    def __init__(self, settings):
        self._admin_chat_id = int(settings['Admin']['admin_chat_id'])
        self._admin_pin_code = '1234'  # save it with something like keyring

        self._sender = Sender(settings)
        self._ether_scan = EtherScan(settings)
        self._data_storage = DataStorage(settings)
        self._templates_env = Environment(loader=FileSystemLoader(settings['Admin']['admin_responses_path']))

        self._admin_sessions_list = []
        self._auth_queries = []
        self._max_auth_tries = int(settings['Admin']['max_auth_tries'])

        self._commands = ['/set_wallet', '/set_fee', '/set_vote_end_time', '/admin_cancel',
                          '/stat', '/pay_out']

    def _has_active_session(self, chat_id: int) -> bool:
        for n, session in enumerate(self._admin_sessions_list):
            if session['chat_id'] == chat_id:
                if session['login_time'] - datetime.utcnow() >= timedelta(minutes=30):
                    del (self._admin_sessions_list[n])
                    return False

                return True

        return False

    def is_authorize_query(self, message: dict) -> bool:
        try:
            chat_id = message['message']['from']['id']
        except KeyError:
            return False

        return not self._find_auth_query_index(chat_id) == -1

    def _check_auth_info(self):
        valid_auth_queries = []
        valid_sessions = []

        for n, auth_query in enumerate(self._auth_queries):
            if auth_query['creation_time'] - datetime.utcnow() < timedelta(minutes=5):
                valid_auth_queries.append(self._auth_queries[n])

        self._auth_queries = valid_auth_queries

        for n, session in enumerate(self._admin_sessions_list):
            if datetime.utcnow() - session['login_time'] < timedelta(minutes=30):
                valid_sessions.append(self._admin_sessions_list[n])

        self._admin_sessions_list = valid_sessions

    def handle_command(self, command: dict):
        self._check_auth_info()

        chat_id = command['message']['from']['id']

        if command['message']['chat']['id'] != self._admin_chat_id:
            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('default_answer_command.jinja').render(),
                                      reply_markup=self._data_storage.basic_keyboard)
            return

        if not self._has_active_session(chat_id):
            self._auth_queries.append({'chat_id': chat_id, 'tries': self._max_auth_tries,
                                       'creation_time': datetime.utcnow(), 'action_after_auth': command})

            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('authorize_message_chat.jinja').render())
            self._sender.send_message(chat_id,
                                      self._templates_env.get_template('authorize_message_personally.jinja').render())
            return

        else:
            text = command['message']['text'].split()
            command_type = text[0]
            args = text[1:]

            if command_type == '/set_wallet':
                self._set_wallet(args)
            elif command_type == '/set_fee':
                self._set_fee(args)
            elif command_type == '/set_vote_end_time':
                self._set_vote_end_time(args)
            elif command_type == '/stat':
                self._statistics()
            elif command_type == '/pay_out':
                pass
            elif command_type == 'admin_cancel':
                pass

    def _statistics(self):
        statistics_message = self._templates_env.get_template('statistics_message.jinja')

        confirmed_A = self._data_storage.count_confirmed_bets('A')
        confirmed_B = self._data_storage.count_confirmed_bets('B')

        unconfirmed_A = self._data_storage.count_unconfirmed_bets('A')
        unconfirmed_B = self._data_storage.count_unconfirmed_bets('B')

        eth_A = self._data_storage.total_eth('A')
        eth_B = self._data_storage.total_eth('B')

        fee_A = eth_A * self._data_storage.fee
        fee_B = eth_B * self._data_storage.fee

        profit = math.trunc((fee_A + fee_B) * 1000) / 1000

        rate_A, rate_B = self._data_storage.represented_rates

        self._sender.send_message(self._admin_chat_id, statistics_message.render(
            confirmed_A=str(confirmed_A),
            confirmed_B=str(confirmed_B),
            wait_A=str(unconfirmed_A),
            wait_B=str(unconfirmed_B),
            eth_A=str(eth_A),
            eth_B=str(eth_B),
            fee_A=str(fee_A),
            fee_B=str(fee_B),
            rate_A=rate_A,
            rate_B=rate_B,
            profit=str(profit)
        ))

    def _set_vote_end_time(self, args: list):
        try:
            hour = int(args[0])
        except ValueError:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_time.jinja').render())
            return
        except IndexError:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_time.jinja').render())
            return

        if hour < 1 or hour > 23:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_time.jinja').render())
            return

        new_time_limit = self._data_storage.time_limit
        new_time_limit.hour = hour

        if datetime.utcnow() > new_time_limit:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_time.jinja').render())
            return

        self._data_storage.time_limit.hour = hour

        self._sender.send_message(self._admin_chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _set_fee(self, args: list):
        try:
            fee = int(args[0])
        except ValueError:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_fee.jinja').render())
            return
        except IndexError:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_fee.jinja').render())
            return

        if fee <= 0 or fee >= 100:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_fee.jinja').render())
            return

        self._data_storage.fee = fee / 100

        self._sender.send_message(self._admin_chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _set_wallet(self, args: list):
        try:
            category = args[0]
            wallet = args[1]
        except IndexError:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_wallet.jinja').render())
            return

        if category not in ['A', 'B']:
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_category.jinja').render())
            return

        if not self._ether_scan.wallet_is_correct(wallet):
            self._sender.send_message(self._admin_chat_id,
                                      self._templates_env.get_template('incorrect_wallet.jinja').render())
            return

        if category == 'A':
            self._data_storage.A_wallet = wallet
        else:
            self._data_storage.B_wallet = wallet
        self._sender.send_message(self._admin_chat_id,
                                  self._templates_env.get_template('info_successfully_changed.jinja').render())

    def _find_auth_query_index(self, chat_id: int) -> int:
        for n, auth_query in enumerate(self._auth_queries):
            if auth_query['chat_id'] == chat_id:
                return n

        return -1

    def auth(self, message: dict):
        chat_id = message['message']['from']['id']
        auth_query_index = self._find_auth_query_index(chat_id)

        if message['message']['text'] == self._admin_pin_code:
            self._admin_sessions_list.append({'chat_id': chat_id, 'login_time': datetime.utcnow()})

            self._sender.send_message(chat_id, self._templates_env.get_template('success_auth.jinja').render())
            self.handle_command(self._auth_queries[auth_query_index]['action_after_auth'])
            del (self._auth_queries[auth_query_index])

        else:
            self._sender.send_message(chat_id, self._templates_env.get_template('incorrect_pin.jinja').render())
            self._auth_queries[auth_query_index]['tries'] -= 1

            if self._auth_queries[auth_query_index]['tries'] == 0:
                del (self._auth_queries[auth_query_index])
                self._sender.send_message(chat_id,
                                          self._templates_env.get_template('create_new_auth_query.jinja').render())
