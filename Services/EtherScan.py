from string import ascii_letters


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

    def _get_transactions(self):
        pass

    def check_transaction(self):
        pass
        # HINT: to check transaction we can get this page: https://etherscan.io/address/{address} and parse it
