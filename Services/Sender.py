import requests
import json


class Sender:
    def __init__(self, access_token):
        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'

        self._reply_keyboard = {'keyboard': [[{'text': '/howMany'}],
                                             [{'text': '/currentRound'}],
                                             [{'text': '/bet'}],
                                             [{'text': '/help'}]]}

        self._reply_keyboard_hide = {'hide_keyboard': True}

    def send_reply_keyboard(self, chat_id, text):
        reply_markup = json.dumps(self._reply_keyboard)

        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': text,
                                  'reply_markup': reply_markup})

    def send(self, chat_id, text, reply_keyboard_hide=False):
        if reply_keyboard_hide:
            response = requests.post(self._requests_url + 'sendMessage',
                                     {'chat_id': chat_id, 'text': text,
                                      'reply_markup': json.dumps(self._reply_keyboard_hide)})
            print(response.text)
        else:
            response = requests.post(self._requests_url + 'sendMessage',
                                     {'chat_id': chat_id, 'text': text})

    def send_with_reply_markup(self, chat_id, text, reply_markup):
        reply_markup = json.dumps({'inline_keyboard': reply_markup})
        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': text,
                                  'reply_markup': reply_markup})

    def answer_callback_query(self, chat_id, callback_query_id, text):
        if text:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id, 'text': text})
        else:
            response = requests.post(self._requests_url + 'answerCallbackQuery',
                                     {'chat_id': chat_id, 'callback_query_id': callback_query_id})
