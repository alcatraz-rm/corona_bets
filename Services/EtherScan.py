from string import ascii_letters
import requests


class EtherScan:
    def __init__(self):
        pass

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

    def check_transaction(self):
        pass
        # HINT: to check transaction we can get this page: https://etherscan.io/address/{address} and parse it
       # response = requests.get(f'https://api.etherscan.io/api?module=proxy&action=eth_getStorageAt&address=0xc758512Fa72021820ab9f04DceA196269baF182e&position=0x0&tag=latest&apikey={self.api_token}')
