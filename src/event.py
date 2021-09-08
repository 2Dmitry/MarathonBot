from enum import Enum
from datetime import datetime
import logging

SYMBOLS = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
           u"abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA")
tr = {ord(a):ord(b) for a, b in zip(*SYMBOLS)}


DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'

class EVENT_STATUS(Enum):
    NEW = 1
    IN_PROGRESS = 2
    TYPE_NOT_DEFINED = 3
    SPORT_NOT_DEFINED = 4
    CANT_CONSTRUCT_STRING = 5
    NO_SEARCH_RESULTS = 6
    EVENT_HAS_ALREADY_BEGUN = 7
    MARKET_TABLE_NOT_FOUND = 8
    MARKET_NOT_FOUND = 9
    NOT_TRY_COUPON_COEFF = 10
    COEFFICIENT_DOES_NOT_EXIST_IN_MARKET = 11
    BET_ACCEPTED = 12
    def __str__(self) -> str:
        return self.name.lower().replace('_', ' ')
    

class Event:
    def __init__(self, text: str, tg_message_unix_date: datetime, event_id: int) -> None:
        self.id = event_id
        self.status = EVENT_STATUS.NEW
        self.desc = None
        self.date_last_try = '0000-00-00_00-00-00'
        self.processing_time = None
        self.date_bet_accept = None 
        self.time_event_start = None
        self.date_message_send = tg_message_unix_date
        self.date_added = datetime.now().strftime(DATE_FORMAT)
        self.__parse_text(text)
        self.markets_table_name = None
        self.winner_team = None
        self.market_str = None
        self.coupon_coeff = None
        self.history_coeff = []
        logging.info(f'Put event in queue: {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}')
        print(f'Put event in queue: {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}')

    def __parse_text(self, text: str) -> None:
        self.sport = text[:text.find(';')]
        text = text[text.find(';') + 2:]                                        # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
        self.league = text[text.find(':') + 2:text.find(';')]                   # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
        text = text[text.find(';') + 2:]                                        # Ранхейм vs Фредрикстад: O(1)=1.57;

        delimiter_team = ' vs '
        indent = 4
        if text.find(delimiter_team) == -1:
            delimiter_team = ' - '
            indent = 3

        self.team1 = text[:text.find(delimiter_team)]                           # Ранхейм vs Фредрикстад: O(1)=1.57;
        self.team1_eng = self.team1.translate(tr)
        self.team2 = text[text.find(delimiter_team) + indent:text.find(':')]    # Ранхейм vs Фредрикстад: O(1)=1.57;
        self.team2_eng = self.team2.translate(tr)
        text = text[text.find(':') + 2:]                                        # O(1)=1.57;
        self.type = text[:text.find('=')]                                       # O(1)=1.57;
        self.coeff = float(text[text.find('=') + 1:text.find(';')])             # O(1)=1.57;
        
    def __str__(self) -> str:
        return self.__dict__.__str__()

    def __repr__(self) -> str:
        return self.__dict__

    def to_json(self) -> dict:
        logging.info(f"obj dict is {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}")
        json_dict = {}
        for key, value in self.__dict__.items():
            json_dict[key] = value
            if isinstance(self.__dict__[key], EVENT_STATUS):
                json_dict[key] = str(value)
        return json_dict