import datetime

import requests
from bs4 import BeautifulSoup


class StatisticsParser:
    def __init__(self):
        self._event_url = 'https://xn--80aesfpebagmfblc0a.xn--p1ai/'
        self._date_selector = '#operational-data > div.cv-banner__left > div'
        self._day_selector = '#app > article > section.cv-banner > div > div > div.cv-banner__bottom > ' \
                             'div.cv-countdown > div:nth-child(3) > div.cv-countdown__item-value._accent > span'
        self._total_selector = '#app > article > section.cv-banner > div > div > div.cv-banner__bottom > ' \
                               'div.cv-countdown > div:nth-child(2) > div.cv-countdown__item-value._accent > span'

    def update(self) -> dict:
        response = requests.get(self._event_url)
        soup = BeautifulSoup(response.text, 'lxml')

        return {'day': int(soup.select(self._day_selector)[0].text.replace(' ', '')),
                'total': int(soup.select(self._total_selector)[0].text.replace(' ', '')),
                'date': self._parse_date(soup.select(self._date_selector)[0].text)}

    def event_check(self, control_value: int):
        return self.update()['day'] != control_value

    @staticmethod
    def _parse_date(date: str):
        year = 2020
        day_tmp = date.split()[3]

        month_name = date.split()[4].lower()

        if month_name == 'января':
            month = 1
        elif month_name == 'февраля':
            month = 2
        elif month_name == 'марта':
            month = 3
        elif month_name == 'апреля':
            month = 4
        elif month_name == 'мая':
            month = 5
        elif month_name == 'июня':
            month = 6
        elif month_name == 'июля':
            month = 7
        elif month_name == 'августа':
            month = 8
        elif month_name == 'сентября':
            month = 9
        elif month_name == 'октября':
            month = 10
        elif month_name == 'ноября':
            month = 11
        elif month_name == 'декабря':
            month = 12
        else:
            print("Can't decode month")
            return

        if day_tmp.startswith('0'):
            day = int(day_tmp[1])
        else:
            day = int(day_tmp)

        time = date.split()[5].split(':')
        hours = time[0]
        minutes = time[1]

        if hours.startswith('0'):
            hours = int(hours[1])
        else:
            hours = int(hours)

        if minutes.startswith('0'):
            minutes = int(minutes[1])
        else:
            minutes = int(minutes)

        return datetime.datetime(year, month, day, hours, minutes)
