from Services.Singleton import Singleton
from Services.EventParser import EventParser


class DataKeeper(metaclass=Singleton):
    def __init__(self):
        self._event_parser = EventParser()

        self._list_A = []
        self._list_B = []

        self._rate = 0
        self._fee = 0

        self._cases_all = None
        self._cases_day = None
        self._date = None

    def update(self):
        data = self._event_parser.update()

        self._cases_all = data['total']
        self._cases_day = data['day']
        self._date = data['date']

    def get_cases_day(self): return self._cases_day

    def get_cases_all(self): return self._cases_all

    def get_date(self): return self._date

    def get_rate(self): return self._rate
