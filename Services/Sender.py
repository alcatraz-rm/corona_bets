import requests
import json
import logging
from pprint import pprint


class Sender:
    def __init__(self, access_token):
        self._logger = logging.getLogger('Engine.Sender')

        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'

        self._logger.info('Sender initialized.')

    def _log_telegram_response(self, response):
        result = {'ok': response['ok']}

        if 'username' in response['result']['chat']:
            result['to'] = {'chat_id': response['result']['chat']['id'],
                            'username': response['result']['chat']['username'],
                            'text': response['result']['text'], 'message_id': response['result']['message_id']}
        else:
            result['to'] = {'chat_id': response['result']['chat']['id'],
                            'text': response['result']['text'], 'message_id': response['result']['message_id']}

        self._logger.info(f'Sent: {json.dumps(result, indent=4, ensure_ascii=False)}')

    def answer_callback_query(self, chat_id, callback_query_id, text):
        if text:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id, 'text': text})
        else:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id})

        self._logger.info(f'Answer callback query: {response.json()}')

        self._logger.info(response.json())

    def send_photo(self, chat_id, photo):
        response = requests.post(self._requests_url + 'sendPhoto', {'chat_id': chat_id, 'photo': photo}, )
        self._logger.info(response.json())

    def send(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        if reply_markup:
            response = requests.post(self._requests_url + 'sendMessage',
                                     params={'chat_id': chat_id, 'text': text,
                                             'reply_markup': reply_markup, 'parse_mode': parse_mode}).json()
        else:
            response = requests.post(self._requests_url + 'sendMessage',
                                     params={'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}).json()

        self._log_telegram_response(response)


# TODO: add Telegram answer logger

