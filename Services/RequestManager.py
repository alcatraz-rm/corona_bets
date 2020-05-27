import requests


class RequestManager:
    def __init__(self):
        pass

    @staticmethod
    def request(url, params, method):
        try:
            if method == 'get':
                return requests.get(url, params)
            elif method == 'post':
                return requests.post(url, params)
            else:
                return 'Invalid http-method.'

        except requests.exceptions.HTTPError as exception:
            return exception

        except requests.exceptions.ConnectTimeout as exception:
            return exception

        except requests.exceptions.Timeout as exception:
            return exception

        except requests.exceptions.ConnectionError as exception:
            return exception

        except requests.exceptions.RequestException as exception:
            return exception

        except Exception as exception:
            return exception
