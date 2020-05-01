
class CommandHandler:
    def __init__(self):
        self._required_commands = ['/start', '/help']
        self._default_answer = "Sorry, I don't know this command."

    def handle(self, command_object):
        command = command_object['message']['text']

        if command in self._required_commands:
            if command == '/start':
                return "Welcome!"
            elif command == '/help':
                return "I would be happy to help, but I can't do anything yet, so there's nothing to help with."

        return self._default_answer
