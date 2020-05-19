from pprint import pprint
from string import ascii_letters

import requests


class EtherScan:
    def __init__(self):
        self._requests_url = 'http://api.etherscan.io/api'
        self._api_key = 'XJZ6BA37G1DG5MVJQQ4Z6SBRAK6FXCWMB1'

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

    def _get_transactions(self, address):
        params = {'module': 'account', 'action': 'txlist', 'address': address, 'start_block': 0,
                  'end_block': 99999999, 'page': 1, 'offset': 20, 'sort': 'desc', 'apikey': self._api_key}
        response = requests.get(self._requests_url, params=params).json()['result']

        return [{'from': transaction['from'], 'to': transaction['to'], 'amount': int(transaction['value']) / (10 ** 18),
                 'hash': transaction['hash'], 'timestamp': transaction['timeStamp']} for transaction in response]

    # TODO: remember incorrect transactions
    def check_transactions(self, address, from_, to):
        transactions = self._filter_transactions(from_, to, self._get_transactions(address))
        pprint(transactions)

    @staticmethod
    def _filter_transactions(from_, to, transactions):
        result = []

        for transaction in transactions:
            if transaction['from'] == from_ and transaction['to'] == to:
                result.append(transaction)

        return result

#
# scan = EtherScan()
# result = scan._get_transactions('0x79289bb6b441cd337e2ad22b8f8202661d7b53f4')
# pprint(result)
