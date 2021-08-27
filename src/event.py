from datetime import datetime
from enum import Enum

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
        self.status = EVENT_STATUS.NEW
        self.id = None
        self.date_message_send = tg_message_unix_date
        self.date_added = datetime.now().strftime(DATE_FORMAT)
        self.date_bet_accept = None
        self.date_last_try = '0000-00-00_00-00-00'
        self.time_event_start = None
        self.processing_time = None
        self.desc = None
        self.sport = text[:text.find(';')]
