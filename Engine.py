import requests
import tornado.web, tornado.escape, tornado.ioloop
# import logging
import signal
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

    def send_reply(self, response):
        if 'text' in response:
            self._current_session.post(self._requests_url + "sendMessage", data=response)

    def _hello(self):
        pass

    def _help(self):
        pass

    def _backup(self):
        pass

    def _add_user_to_table(self):
        pass

    @staticmethod
    def _signal_term_handler(signum, frame):
        pass

    def launch(self):
        signal.signal(signal.SIGTERM, self._signal_term_handler)
        try:
   #         set_hook = self._current_session.get(self._requests_url + "setWebhook?url=%s" % self._myURL)
    #        if set_hook.status_code != 200:
     #           logging.error("Can't set hook: %s. Quit." % set_hook.text)
      #          exit(1)
            self._application.listen(8888)
            tornado.ioloop.IOLoop.current().start()
        except KeyboardInterrupt:
            self._signal_term_handler(signal.SIGTERM, None)
