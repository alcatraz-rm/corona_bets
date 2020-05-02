from bs4 import BeautifulSoup
import requests


class EventParser:
    def __init__(self):
        self._event_url = 'https://xn--80aesfpebagmfblc0a.xn--p1ai/'
        self._date_selector = '#operational-data > div.cv-banner__left > div'
        self._russia_day_selector = '#app > article > section.cv-banner > div > div > div.cv-banner__bottom > ' \
                                    'div.cv-countdown > div:nth-child(3) > div.cv-countdown__item-value._accent > span'
        self._russia_all_selector = '#app > article > section.cv-banner > div > div > div.cv-banner__bottom > ' \
                                    'div.cv-countdown > div:nth-child(2) > div.cv-countdown__item-value._accent > span'

    def update(self):
        response = requests.get(self._event_url)
        soup = BeautifulSoup(response.text, 'lxml')

        return int(soup.select(self._russia_day_selector)[0].text.replace(' ', ''))

    def update_all(self):
        response = requests.get(self._event_url)
        soup = BeautifulSoup(response.text, 'lxml')

        return {'day': soup.select(self._russia_day_selector)[0].text,
                'total': soup.select(self._russia_all_selector)[0].text,
                'date': soup.select(self._date_selector)[0].text}
