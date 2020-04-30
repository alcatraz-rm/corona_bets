import requests
import tornado.web, tornado.escape, tornado.ioloop
# import logging
import signal
from pprint import pprint
from RequestHandler import Handler


class Engine:
    def __init__(self, access_token):
        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'
        self._myURL = '127.0.0.1'
        self._current_session = requests.Session()
        self._application = tornado.web.Application([(r"/", Handler), ])

        self._fee = 0
        self._rate = 0
        self._list_A = []
        self._list_B = []

    # user model: {'login': "", 'name': ""}

    def _get_updates(self, offset=None, timeout=30):
        return requests.get(self._requests_url + 'getUpdates',
                            {'timeout': timeout, 'offset': offset}).json()['result']

    def _get_last_update(self):
        result = self._get_updates()
        last_update = None

        if len(result) > 0:
            last_update = result[-1]

        return last_update

    def _hello(self, chat_id):
        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': 'Hello!'})

    def _help(self):
        pass

    def _backup(self):
        pass

    def _add_user_to_table(self):
        pass

    @staticmethod
    def _signal_term_handler(signum, frame):
        pass

    def launch_long_polling(self):
        new_offset = None

        while True:
            self._get_updates(new_offset)
            last_update = self._get_last_update()
            pprint(last_update)

            if last_update:
                last_update_id = last_update['update_id']

                chat_id = last_update['message']['chat']['id']
                self._hello(chat_id)

                new_offset = last_update_id + 1

    def launch_hook(self):
        signal.signal(signal.SIGTERM, self._signal_term_handler)
        try:
            set_hook = self._current_session.get(self._requests_url + "setWebhook?url=%s" % self._myURL)
            if set_hook.status_code != 200:
                print("Can't set hook: %s. Quit." % set_hook.text)
                exit(1)
            self._application.listen(8888)
            tornado.ioloop.IOLoop.current().start()
        except KeyboardInterrupt:
            self._signal_term_handler(signal.SIGTERM, None)
