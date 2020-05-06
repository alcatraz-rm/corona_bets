import tornado.web, tornado.escape, tornado.ioloop
from pprint import pprint


class Handler(tornado.web.RequestHandler):
    def initialize(self, data_keeper, command_handler, sender):
        print('init')
        self._data_keeper = data_keeper
        self._command_handler = command_handler
        self._sender = sender

    def post(self):
        print(1)
        update = tornado.escape.json_decode(self.request.body)
        pprint(update)

        if update:
            if 'message' in update:
                # chat_id = update['message']['from']['id']

                if self._data_keeper.is_new_user(update):
                    self._data_keeper.add_user(update)

                # last_update_id = update['update_id']

                if update['message']['text'].startswith('/'):
                    self._command_handler.handle_command(update)
                else:
                    self._command_handler.handle_text_message(update)

            elif 'callback_query' in update:
                # last_update_id = update['update_id']
                chat_id = update['callback_query']['from']['id']
                state = self._data_keeper.get_state(chat_id)

                if state:
                    self._command_handler.handle_state(chat_id, state, update)
                else:
                    self._sender.answer_callback_query(chat_id, update['callback_query']['id'], '')
                    
    def get(self):
        print('get')

