import requests
from requests.adapters import HTTPAdapter


# TODO: add info like timeout and retries to config
class RequestManager:
    def __init__(self, settings):
        self._basic_http_adapter = HTTPAdapter(max_retries=int(settings['RequestManager']['max_retries']))
        self._session = requests.Session()
        self._basic_timeout = int(settings['RequestManager']['basic_timeout'])
        self._session.mount(settings['General']['telegram_requests_url'], self._basic_http_adapter)

    def request(self, url: str, params: dict, method: str):
        try:
            if method == 'get':
                return self._session.get(url, params=params, timeout=self._basic_timeout)
            elif method == 'post':
                return self._session.post(url, params=params, timeout=self._basic_timeout)
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
