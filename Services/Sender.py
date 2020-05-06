import requests
import json
import logging
from pprint import pprint


class Sender:
    def __init__(self, access_token):
        self._logger = logging.getLogger('Engine.Sender')

        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'

        self._reply_keyboard = {'keyboard': [[{'text': '/howMany'}],
                                             [{'text': '/currentRound'}],
                                             [{'text': '/bet'}],
                                             [{'text': '/help'}]]}

        self._reply_keyboard_hide = {'hide_keyboard': True}

        self._logger.info('Sender initialized.')

    def send_reply_keyboard(self, chat_id, text):
        reply_markup = json.dumps(self._reply_keyboard)

        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': text,
                                  'reply_markup': reply_markup})

        self._logger.info(response.json())

    def send(self, chat_id, text, reply_keyboard_hide=False):
        if reply_keyboard_hide:
            response = requests.post(self._requests_url + 'sendMessage',
                                     {'chat_id': chat_id, 'text': text,
                                      'reply_markup': json.dumps(self._reply_keyboard_hide)})
        else:
            response = requests.post(self._requests_url + 'sendMessage',
                                     {'chat_id': chat_id, 'text': text})

        self._logger.info(response.json())

    def send_with_reply_markup(self, chat_id, text, reply_markup):
        reply_markup = json.dumps({'inline_keyboard': reply_markup})
        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': text,
                                  'reply_markup': reply_markup})
        self._logger.info(response.json())

    def answer_callback_query(self, chat_id, callback_query_id, text):
        if text:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id, 'text': text})
        else:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id})

        self._logger.info(response.json())

    def send_photo(self, chat_id, photo):
        response = requests.post(self._requests_url + 'sendPhoto', {'chat_id': chat_id, 'photo': photo}, )
        self._logger.info(response.json())

# TODO: add Telegram answer logger

