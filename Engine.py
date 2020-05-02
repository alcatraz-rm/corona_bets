import requests
# import tornado.web, tornado.escape, tornado.ioloop
# import logging
# import signal
from pprint import pprint
import datetime

# from RequestHandler import Handler
from CommandHandler import CommandHandler
from EventParser import EventParser


class Engine:
    def __init__(self, access_token):
        self._access_token = access_token
        self._requests_url = f'https://api.telegram.org/bot{access_token}/'
        # self._myURL = '127.0.0.1'
        # self._current_session = requests.Session()
        # self._application = tornado.web.Application([(r"/", Handler), ])
        self._command_handler = CommandHandler()
        self._event_parser = EventParser()

        self._date = None
        self._cases = None
        self._fee = 0
        self._rate = 0
        self._list_A = []
        self._list_B = []

        self._update_info()

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

    def _update_info(self):
        data = self._event_parser.update_all()
        self._cases = data['day']
        self._date = self._parse_date(data['date'])
        print(self._date)

    @staticmethod
    def _parse_date(date):
        year = 2020
        day_tmp = date.split()[3]

        month_name = date.split()[4].lower()

        if month_name == 'января':
            month = 1
        elif month_name == 'февраля':
            month = 2
        elif month_name == 'марта':
            month = 3
        elif month_name == 'апреля':
            month = 4
        elif month_name == 'мая':
            month = 5
        elif month_name == 'июня':
            month = 6
        elif month_name == 'июля':
            month = 7
        elif month_name == 'августа':
            month = 8
        elif month_name == 'сентября':
            month = 9
        elif month_name == 'октября':
            month = 10
        elif month_name == 'ноября':
            month = 11
        elif month_name == 'декабря':
            month = 12
        else:
            print("Can't decode month")
            return

        if day_tmp.startswith('0'):
            day = int(day_tmp[1])
        else:
            day = int(day_tmp)

        time = date.split()[5].split(':')
        hours = time[0]
        minutes = time[1]

        if hours.startswith('0'):
            hours = int(hours[1])
        else:
            hours = int(hours)

        if minutes.startswith('0'):
            minutes = int(minutes[1])
        else:
            minutes = int(minutes)

        return datetime.datetime(year, month, day, hours, minutes)

    def _hello(self, chat_id):
        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': 'Hello!'})

    def _send_reply(self, chat_id, text):
        response = requests.post(self._requests_url + 'sendMessage',
                                 {'chat_id': chat_id, 'text': text})

    def _help(self, chat_id):
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

        try:
            while True:
                self._get_updates(new_offset)
                last_update = self._get_last_update()
                pprint(last_update)

                if last_update:
                    last_update_id = last_update['update_id']
                    chat_id = last_update['message']['from']['id']

                    if last_update['message']['text'].startswith('/'):
                        answer = self._command_handler.handle(last_update)

                        self._send_reply(chat_id, answer)
                        # self._hello(chat_id)
                    else:
                        self._hello(chat_id)

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
