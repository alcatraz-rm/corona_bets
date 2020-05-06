import requests
import logging
from datetime import datetime
import os
import platform
import json
import signal
import tornado.web, tornado.escape, tornado.ioloop

# import logging
from pprint import pprint

# from RequestHandler import Handler
from Services.CommandHandler import CommandHandler
from Services.EventParser import EventParser
from Services.DataKeeper import DataKeeper
from Services.Sender import Sender

from Services.Handler import Handler


class Engine:
    def __init__(self, access_token):
        self._logger = logging.getLogger('Engine')
        self._configure_logger()

        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'

        self._command_handler = CommandHandler(self._access_token)
        self._event_parser = EventParser()
        self._sender = Sender(self._access_token)
        self._data_keeper = DataKeeper()
        self._data_keeper.update()

        self._application = tornado.web.Application([
            (r"/",
             Handler,
             dict(data_keeper=self._data_keeper, command_handler=self._command_handler, sender=self._sender)),
        ])

        self._logger.info('Engine initialized.')

    def _configure_logger(self):
        self._logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("log.log", "w", "utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(fh)

        self._logger.info(f'Platform: {platform.system().lower()}')
        self._logger.info(f'WD: {os.getcwd()}')

    def _get_updates(self, offset=None, timeout=10):
        return requests.get(self._requests_url + 'getUpdates',
                            {'timeout': timeout, 'offset': offset}).json()['result']

    def _log_update(self, update):
        log_message = {}

        if 'message' in update:
            log_message['type'] = 'message'

            chat_id = update['message']['from']['id']
            log_message['from'] = {'chat_id': chat_id}

            if 'last_name' in update['message']['from']:
                name = f"{update['message']['from']['first_name']} {update['message']['from']['last_name']}"
            else:
                name = f"{update['message']['from']['first_name']}"

            log_message['from']['name'] = name

            if 'username' in update['message']['from']:
                log_message['from']['username'] = update['message']['from']['username']

            log_message['text'] = update['message']['text']
            log_message['update_id'] = update['update_id']

        elif 'callback_query' in update:
            log_message['type'] = 'callback_query'
            log_message['from'] = {'chat_id':  update['callback_query']['from']['id']}

            if 'last_name' in update['callback_query']['from']:
                name = f"{update['callback_query']['from']['first_name']} " \
                       f"{update['callback_query']['from']['last_name']}"
            else:
                name = f"{update['callback_query']['from']['first_name']}"

            log_message['from']['name'] = name

            if 'username' in update['callback_query']['from']:
                log_message['from']['username'] = update['callback_query']['from']['username']

            log_message['update_id'] = update['update_id']
            log_message['callback_query_id'] = update['callback_query']['id']
            log_message['data'] = update['callback_query']['data']

        else:
            log_message = update

        self._logger.info(f'New update: {json.dumps(log_message, indent=4, ensure_ascii=False)}')

    def launch_long_polling(self):
        self._logger.info('Launching long polling...')

        new_offset = None

        try:
            while True:
                updates = self._get_updates(new_offset)
                for update in updates:
                    # pprint(update)

                    self._log_update(update)

                    if update:
                        if 'message' in update:
                            chat_id = update['message']['from']['id']

                            if self._data_keeper.is_new_user(update):
                                self._data_keeper.add_user(update)

                            last_update_id = update['update_id']

                            if update['message']['text'].startswith('/'):
                                self._command_handler.handle_command(update)
                            else:
                                self._command_handler.handle_text_message(update)

                            new_offset = last_update_id + 1

                        elif 'callback_query' in update:
                            last_update_id = update['update_id']
                            chat_id = update['callback_query']['from']['id']
                            state = self._data_keeper.get_state(chat_id)

                            if state:
                                self._command_handler.handle_state(chat_id, state, update)
                            else:
                                self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')

                            new_offset = last_update_id + 1

        except KeyboardInterrupt:
            self._logger.info('Keyboard interrupt occurred. Quit.')
            exit(0)

    def launch_hook(self, address):
        self._logger.info('Launching webhook...')
        self._logger.debug(address)

        signal.signal(signal.SIGTERM, self._signal_term_handler)

        try:
            print(self._requests_url + "setWebhook?url=%s" % address)
            set_hook = requests.get(self._requests_url + "setWebhook?url=%s" % address)
            pprint(set_hook.json())
            self._logger.debug(set_hook.json())

            if set_hook.status_code != 200:
                self._logger.error(f"Can't set hook to address: {address}")
                exit(1)

            self._logger.info('Start listening...')

            self._application.listen(port=80, address='')
            tornado.ioloop.IOLoop.current().start()

        except KeyboardInterrupt:
            self._logger.info('Keyboard interrupt occurred. Deleting webhook...')
            self._signal_term_handler(signal.SIGTERM, None)

    def _signal_term_handler(self, signum, frame):
        response = requests.post(self._requests_url + "deleteWebhook")
        self._logger.debug(response.json())
        self._logger.info('Webhook was successfully deleted.')
