import json
import logging

import requests

from Services.RequestManager import RequestManager


class Sender:
    def __init__(self, telegram_access_token):
        self._logger = logging.getLogger('Engine.Sender')
        self._request_manager = RequestManager()
        self._requests_url = f'https://api.telegram.org/bot{telegram_access_token}/'

        self._logger.info('Sender initialized.')

    def _log_telegram_response(self, response):
        result = {'ok': response['ok']}

        if not 'result' in response or not 'chat' in response['result']:
            self._logger.warning(response)
            return

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
            response = self._request_manager.request(self._requests_url + 'answerCallbackQuery',
                                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id,
                                                      'text': text}, method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for answer callback query: {response.json()}')
            else:
                self._logger.error(f'Error occurred during answering callback query: {response}')
                self.send_message_to_creator(f'Error occurred during answering callback query: {response}')

        else:
            response = self._request_manager.request(self._requests_url + 'answerCallbackQuery',
                                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id},
                                                     method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for answer callback query: {response.json()}')
            else:
                self._logger.error(f'Error occurred during answering callback query: {response}')
                self.send_message_to_creator(f'Error occurred during answering callback query: {response}')

    def send_photo(self, chat_id, photo, reply_markup=None):
        if reply_markup:
            response = self._request_manager.request(self._requests_url + 'sendPhoto',
                                                     {'chat_id': chat_id, 'photo': photo,
                                                      'reply_markup': reply_markup}, method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for answer callback query: {response.json()}')
            else:
                self._logger.error(f'Error occurred during sending photo: {response}')
                self.send_message_to_creator(f'Error occurred during sending photo: {response}')
        else:
            response = self._request_manager.request(self._requests_url + 'sendPhoto',
                                                     {'chat_id': chat_id, 'photo': photo}, method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for answer callback query: {response.json()}')
            else:
                self._logger.error(f'Error occurred during sending photo: {response}')
                self.send_message_to_creator(f'Error occurred during sending photo: {response}')

        self._logger.info(response.json())

    def send_message(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        if reply_markup:
            response = self._request_manager.request(self._requests_url + 'sendMessage',
                                                     params={'chat_id': chat_id, 'text': text,
                                                             'reply_markup': reply_markup, 'parse_mode': parse_mode},
                                                     method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for send_message: {response.json()}')
            else:
                self._logger.error(f'Error occurred during sending message: {response}')
                self.send_message_to_creator(f'Error occurred during sending message: {response}')
        else:
            response = self._request_manager.request(self._requests_url + 'sendMessage',
                                                     params={'chat_id': chat_id, 'text': text,
                                                             'parse_mode': parse_mode}, method='post')

            if isinstance(response, requests.Response):
                self._logger.info(f'Response for send_message: {response.json()}')
            else:
                self._logger.error(f'Error occurred during sending message: {response}')
                self.send_message_to_creator(f'Error occurred during sending message: {response}')

        self._log_telegram_response(response.json())

    def send_message_to_creator(self, message):
        creator_id = 187289003

        self._request_manager.request(self._requests_url + 'sendMessage',
                                      params={'chat_id': creator_id, 'text': message}, method='post')
