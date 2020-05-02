from Services.DataKeeper import DataKeeper


class CommandHandler:
    def __init__(self):
        self._required_commands = ['/start', '/help', '/howmany', '/rate']
        self._default_answer = "Sorry, I don't know this command."
        self._data_keeper = DataKeeper()

    def handle(self, command_object):
        command = command_object['message']['text']

        if command in self._required_commands:
            if command == '/start':
                return self._start()

            elif command == '/help':
                return self._help()

            elif command == '/howmany':
                return self._howmany()

            elif command == '/rate':
                return self._rate()

        return self._default_answer

    @staticmethod
    def _start():
        return "Welcome!"

    @staticmethod
    def _help():
        help_message = 'Up-to date coronavirus information: /howmany\n' \
                       'Rate: /rate'

        return help_message

    def _howmany(self):
        self._data_keeper.update()
        cases_day, cases_all = self._data_keeper.get_cases_day(), self._data_keeper.get_cases_all()
        date = self._data_keeper.get_date()

        return f'\nCases (last 24 hours): {cases_day}\nTotal cases: {cases_all}\nLast update: ' \
               f'{date.strftime("%A, %d %B %Y, %I:%M %p")}'

    def _rate(self):
        return f'Rate: {self._data_keeper.get_rate()}'
