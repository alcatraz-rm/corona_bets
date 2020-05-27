import requests
from requests.adapters import HTTPAdapter


class RequestManager:
    def __init__(self):
        self._basic_http_adapter = HTTPAdapter(max_retries=5)
        self._session = requests.Session()
        self._basic_timeout = 45
        self._session.mount('https://api.telegram.org', self._basic_http_adapter)

    def request(self, url, params, method):
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
