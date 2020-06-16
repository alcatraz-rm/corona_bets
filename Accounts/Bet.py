class Bet:
    def __init__(self, chat_id: int, ID: int, category: str, wallet: str, transaction_id: int = 0):
        self._chat_id = chat_id
        self._id = ID
        self._category = category
        self._wallet = wallet
        self._transaction_id = transaction_id

        self._confirmed = True if transaction_id else False

    @property
    def user(self):
        return self._chat_id

    @property
    def category(self):
        return self._category

    @property
    def wallet(self):
        return self._wallet

    @property
    def confirmed(self):
        return self._confirmed
