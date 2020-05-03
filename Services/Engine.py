import requests
import json
# import tornado.web, tornado.escape, tornado.ioloop
# import logging
# import signal
from pprint import pprint

# from RequestHandler import Handler
from Services.CommandHandler import CommandHandler
from Services.EventParser import EventParser
from Services.DataKeeper import DataKeeper
from Services.Sender import Sender


class Engine:
    def __init__(self, access_token, etherscan_token):
        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'
        # self._myURL = '127.0.0.1'
        # self._current_session = requests.Session()
        # self._application = tornado.web.Application([(r"/", Handler), ])
        self._command_handler = CommandHandler(self._access_token, etherscan_token)
        self._event_parser = EventParser()
        self._sender = Sender(self._access_token)
        self._data_keeper = DataKeeper()
        self._data_keeper.update()

    def _get_updates(self, offset=None, timeout=10):
        return requests.get(self._requests_url + 'getUpdates',
                            {'timeout': timeout, 'offset': offset}).json()['result']

    @staticmethod
    def _signal_term_handler(signum, frame):
        pass

    def launch_long_polling(self):
        new_offset = None

        try:
            while True:
                updates = self._get_updates(new_offset)
                for update in updates:
                    pprint(update)

                    if update:
                        if 'message' in update:
                            if self._data_keeper.is_new_user(update):
                                self._data_keeper.add_user(update)

                            last_update_id = update['update_id']
                            chat_id = update['message']['from']['id']

                            if update['message']['text'].startswith('/'):
                                self._command_handler.handle_command(update)
                            else:
                                self._command_handler.handle_text_message(update)

                            new_offset = last_update_id + 1

                        elif 'callback_query' in update:
                            last_update_id = update['update_id']
                            chat_id = update['callback_query']['from']['id']
                            state = self._data_keeper.get_state(chat_id)

                            self._command_handler.handle_state(chat_id, state, update)

                            new_offset = last_update_id + 1

        except KeyboardInterrupt:
            exit(0)

   # def launch_hook(self):
        #signal.signal(signal.SIGTERM, self._signal_term_handler)
        #try:
       #     set_hook = self._current_session.get(self._requests_url + "setWebhook?url=%s" % self._myURL)
      #      if set_hook.status_code != 200:
       #         print("Can't set hook: %s. Quit." % set_hook.text)
      #          exit(1)
     #       self._application.listen(8888)
    #        tornado.ioloop.IOLoop.current().start()
   #     except KeyboardInterrupt:
 #           self._signal_term_handler(signal.SIGTERM, None)
