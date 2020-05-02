import tornado.web, tornado.escape, tornado.ioloop
# import logging


class Handler(tornado.web.RequestHandler):
    def post(self):
        try:
            print("Got request: %s" % self.request.body)
            update = tornado.escape.json_decode(self.request.body)
            message = update['message']
            text = message.get('text')
            if text:
                print("MESSAGE\t%s\t%s" % (message['chat']['id'], text))

                #if text[0] == '/':
                 #   command, *arguments = text.split(" ", 1)
                   # response = CMD.get(command, not_found)(arguments, message)
                   # logging.info("REPLY\t%s\t%s" % (message['chat']['id'], response))
                   # send_reply(response)
        #except Exception as e:
            #logging.warning(str(e))
        except:
            pass
