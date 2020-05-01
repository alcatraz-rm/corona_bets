
class CommandHandler:
    def __init__(self):
        self._required_commands = ['/start', '/help']

    def handle(self, command_object):
        chat_id = command_object['message']['from']['id']
        command = command_object['message']['text']

        if command not in self._required_commands:
            answer = "Sorry, I don't know this command"
        elif command == '/start':
            answer = "Welcome!"
        elif command == '/help':
            answer = "I would be happy to help, but I can't do anything yet, so there's nothing to help with."

        return answer
