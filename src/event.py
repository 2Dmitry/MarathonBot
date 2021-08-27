from enum import Enum
from datetime import datetime
import logging

DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'

class EVENT_STATUS(Enum):
    NEW = 1
    IN_PROGRESS = 2
    NO_SEARCH_RESULTS = 3
    TYPE_NOT_DEFINED = 4
    SPORT_NOT_DEFINED = 5
    MARKET_NOT_FOUND = 6
    NOT_TRY_COUPON_COEFF = 7
    STATUS_BET_ACCEPTED = 8
    def __str__(self):
        return self.name.lower().replace('_', ' ')

class Event:
    def __init__(self, text: str, tg_message_unix_date: datetime):
        self.id = None
        self.date_bet_accept = None 
        self.time_event_start = None
        self.processing_time = None
        self.desc = None
        self.markets_table_name = None
        self.winner_team = None
        self.market_str = None
        self.coupon_coeff = None
        self.history_coeff = []

        self.status = EVENT_STATUS.NEW
        self.date_message_send = tg_message_unix_date
        self.date_added =  datetime.now().strftime(DATE_FORMAT)
        self.date_last_try = '0000-00-00_00-00-00'
        logging.info(f'Bot takes event: {self.date_message_send}')
        self.__parse_text(text)
        print(self.__dict__, '\n')

    def __parse_text(self, text : str):
        self.sport = text[:text.find(';')]
        # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
        text = text[text.find(';') + 2:]
        # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
        self.league = text[text.find(':') + 2:text.find(';')]
        text = text[text.find(';') + 2:]  # Ранхейм vs Фредрикстад: O(1)=1.57;
        # Ранхейм vs Фредрикстад: O(1)=1.57;
        self.team1 = text[:text.find(' vs ')]
        # Ранхейм vs Фредрикстад: O(1)=1.57;
        self.team2 = text[text.find(' vs ') + 4:text.find(':')]
        text = text[text.find(':') + 2:]  # O(1)=1.57;
        self.type = text[:text.find('=')]  # O(1)=1.57;
        self.coeff = float(
            text[text.find('=') + 1:text.find(';')])  # O(1)=1.57;