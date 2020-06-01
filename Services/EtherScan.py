import logging
from pprint import pprint
from string import ascii_letters

import requests

# TODO: put api token into environment variable and create config with links
from Services.DataStorage import DataStorage
from Services.RequestManager import RequestManager
from Services.Sender import Sender


# TODO: dump all this info to config
class EtherScan:
    def __init__(self, settings):
        self._logger = logging.getLogger('Engine.EtherScan')

        self._requests_url = settings['EtherScan']['etherscan_requests_url']
        self._api_key = settings['EtherScan']['etherscan_api_key']
        self._qr_url = settings['EtherScan']['qr_url']

        self._data_storage = DataStorage(settings)
        self._request_manager = RequestManager(settings)
        self._sender = Sender(settings)

        self._logger.info('EtherScan configured.')

    @staticmethod
    def wallet_is_correct(wallet):
        if not wallet.startswith('0x'):
            return False

        if len(wallet) < 40 or len(wallet) > 44:
            return False

        for symbol in wallet:
            if symbol not in '0123456789' and symbol not in ascii_letters:
                return False

        return True

    def get_qr_link(self, wallet: str) -> str:
        return self._qr_url.replace('#', wallet)

    def _get_transactions(self, wallet: str) -> list:
        params = {'module': 'account', 'action': 'txlist', 'address': wallet, 'start_block': 0,
                  'end_block': 99999999, 'page': 1, 'offset': 1000, 'sort': 'desc', 'apikey': self._api_key}

        response = self._request_manager.request(self._requests_url, params, 'get')

        if isinstance(response, requests.Response):
            response = response.json()['result']

            return [
                {'from': transaction['from'], 'to': transaction['to'], 'amount': int(transaction['value']) / (10 ** 18),
                 'hash': transaction['hash'], 'timestamp': transaction['timeStamp']} for transaction in response]
        else:
            self._logger.error(f'Error occurred while trying to get transactions: {response}')
            self._sender.send_message_to_creator(f'Error occurred while trying to get transactions: {response}')
            return []

    def _filter_transactions(self, to: str, transaction_list: list) -> list:
        result = []
        transaction_list = self._filter_incorrect_transactions(transaction_list)

        for transaction in transaction_list:
            if transaction['to'] == to and self._data_storage.is_new_transaction(transaction['hash']):
                result.append(transaction)

        return result

    def confirm_bets(self, chat_id: int) -> list:
        confirmed_bets = []

        bets_list = self._data_storage.get_unconfirmed_bets(chat_id)
        bets_by_wallets = {}

        if not bets_list:
            return []

        for bet in bets_list:
            if bet['wallet'] not in bets_by_wallets:
                bets_by_wallets[bet['wallet']] = []

            bets_by_wallets[bet['wallet']].append(bet)

        for wallet in bets_by_wallets:
            transactions_list = self._get_transactions(wallet)
            correct_transactions_to_A = self._filter_transactions(self._data_storage.A_wallet, transactions_list)
            correct_transactions_to_B = self._filter_transactions(self._data_storage.B_wallet, transactions_list)

            for bet in bets_by_wallets[wallet]:
                if bet['category'] == 'A' and len(correct_transactions_to_A) > 0:
                    correct_transaction = correct_transactions_to_A[0]
                    transaction_id = self._data_storage.add_transaction(correct_transaction['amount'],
                                                                        correct_transaction['hash'], wallet,
                                                                        correct_transaction['to'], 1)
                    self._data_storage.confirm_bet(bet['bet_id'], transaction_id)
                    del(correct_transactions_to_A[0])
                    confirmed_bets.append(bet)

                elif len(correct_transactions_to_B) > 0:
                    correct_transaction = correct_transactions_to_B[0]
                    transaction_id = self._data_storage.add_transaction(correct_transaction['amount'],
                                                                        correct_transaction['hash'], wallet,
                                                                        correct_transaction['to'], 1)
                    self._data_storage.confirm_bet(bet['bet_id'], transaction_id)
                    del(correct_transactions_to_B[0])
                    confirmed_bets.append(bet)

                else:
                    break

        return confirmed_bets

    def _filter_incorrect_transactions(self, transaction_list: list) -> list:
        result = []

        for transaction in transaction_list:
            if transaction['amount'] != self._data_storage.bet_amount:
                if self._data_storage.is_new_transaction(transaction['hash']):
                    self._data_storage.add_transaction(transaction['amount'], transaction['hash'], transaction['from'],
                                                       transaction['to'], 0)
            else:
                result.append(transaction)

        return result
