import logging
from pprint import pprint
from string import ascii_letters

import requests

# TODO: put api token into environment variable and create config with links
from Services.DataStorage import DataStorage
from Services.RequestManager import RequestManager
from Services.Sender import Sender


class EtherScan:
    def __init__(self, telegram_access_token):
        self._logger = logging.getLogger('Engine.EtherScan')

        self._requests_url = 'http://api.etherscan.io/api'
        self._api_key = 'XJZ6BA37G1DG5MVJQQ4Z6SBRAK6FXCWMB1'
        self._qr_url = 'https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl=#&choe=UTF-8'

        self._data_storage = DataStorage()
        self._request_manager = RequestManager()
        self._sender = Sender(telegram_access_token)

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

    def get_qr_link(self, wallet):
        return self._qr_url.replace('#', wallet)

    def _get_transactions(self, address):
        params = {'module': 'account', 'action': 'txlist', 'address': address, 'start_block': 0,
                  'end_block': 99999999, 'page': 1, 'offset': 20, 'sort': 'desc', 'apikey': self._api_key}

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

    # TODO: remember incorrect transactions
    def check_transactions(self, address, from_, to):
        transaction_list = self._filter_transactions(from_, to, self._get_transactions(address))
        pprint(transaction_list)

    @staticmethod
    def _filter_transactions(from_, to, transaction_list):
        result = []

        for transaction in transaction_list:
            if transaction['from'] == from_ and transaction['to'] == to:
                result.append(transaction)

        return result


wallet = '0x79289bb6b441cd337e2ad22b8f8202661d7b53f4'
