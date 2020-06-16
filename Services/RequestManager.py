import requests
from requests.adapters import HTTPAdapter


class RequestManager:
    def __init__(self, settings):
        self._basic_http_adapter = HTTPAdapter(max_retries=int(settings['RequestManager']['max_retries']))
        self._session = requests.Session()
        self._basic_timeout = int(settings['RequestManager']['basic_timeout'])

        self._session.mount(settings['General']['telegram_requests_url'], self._basic_http_adapter)
        self._session.mount(settings['EtherScan']['etherscan_requests_url'], self._basic_http_adapter)
        self._session.mount(settings['StatisticsParser']['statistics_url'], self._basic_http_adapter)

    def request(self, url: str, params: dict, method: str, files: dict = None):
        try:
            if method == 'get':
                if len(params) > 0:
                    return self._session.get(url, params=params, timeout=self._basic_timeout)
                return self._session.get(url, timeout=self._basic_timeout)
            elif method == 'post':
                if len(params) > 0 and files:
                    return self._session.post(url, params=params, timeout=self._basic_timeout, files=files)
                elif files:
                    return self._session.post(url, timeout=self._basic_timeout, files=files)
                elif len(params) > 0:
                    return self._session.post(url, params=params, timeout=self._basic_timeout)

                return self._session.post(url, timeout=self._basic_timeout)
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
