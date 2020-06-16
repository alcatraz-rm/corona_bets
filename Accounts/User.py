class User:
    def __init__(self, name: str, chat_id: int, lang: str, last_wallet: str = None, login: str = None):
        self._name = name
        self._login = login
        self._chat_id = chat_id
        self._last_wallet = last_wallet
        self._lang = lang

    @property
    def name(self):
        return self._name

    @property
    def login(self):
        return self._login

    @property
    def chat_id(self):
        return self._chat_id

    @property
    def last_wallet(self):
        return self._last_wallet

    @last_wallet.setter
    def last_wallet(self, wallet):
        # check_wallet
        self._last_wallet = wallet
        # update in table

    @property
    def lang(self):
        return self._lang
