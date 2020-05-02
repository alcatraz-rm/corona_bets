from EventParser import EventParser


class CommandHandler:
    def __init__(self):
        self._required_commands = ['/start', '/help', '/howmany']
        self._default_answer = "Sorry, I don't know this command."
        self._event_parser = EventParser()

    def handle(self, command_object):
        command = command_object['message']['text']

        if command in self._required_commands:
            if command == '/start':
                return "Welcome!"
            elif command == '/help':
                return "I would be happy to help, but I can't do anything yet, so there's nothing to help with."
            elif command == '/howmany':
                data = self._event_parser.update_all()
                return f'Оперативные данные {data["date"].lower()}:\nСлучаев за последние сутки: ' \
                       f'{data["day"]}\nОбщее число случаев: {data["total"]}'

        return self._default_answer
