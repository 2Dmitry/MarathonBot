from enum import Enum
from datetime import datetime
import logging

from src.utils import logger_info_wrapper

SYMBOLS = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
           u"abvgdeejzijklmnoprstufhzcss_y'euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y'EUA")
tr = {ord(a): ord(b) for a, b in zip(*SYMBOLS)}
DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'


@logger_info_wrapper
def collect_handicap_str(text, handicap_value):
    if text == 'asia':
        if handicap_value < 0:
            text = f'({handicap_value + 0.25},{handicap_value - 0.25})'
            if handicap_value + 0.25 == 0:
                text = f'(0,{handicap_value - 0.25})'
            pass
        if handicap_value > 0:
            text = f'(+{handicap_value - 0.25},+{handicap_value + 0.25})'
            if handicap_value - 0.25 == 0:
                text = f'(0,+{handicap_value + 0.25})'
            pass
    elif text == 'simple':  # обычная фора
        if handicap_value == 0:
            text = '(0)'
        if handicap_value < 0:
            text = f'({handicap_value})'
        if handicap_value > 0:
            text = f'(+{handicap_value})'
        pass
    return text


@logger_info_wrapper
def collect_total_str(text, total_value):
    if text == 'asia':
        text = f'({total_value - 0.25},{total_value + 0.25})'
    elif text == 'simple':  # тотала 0 не бывает, минимум 0.5 и только положительный
        text = f'({total_value})'
    return text


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
    FAKE_BET_ACCEPTED = 13
    RE_BET = 14
    CUT = 15
    BIG_BAR_NOT_FOUND = 16
    EVENT_NOT_FOUND_IN_THE_SPORT_TAB = 17
    MARKET_FOUND = 18
    MARKET_NOT_INTERACTABLE_EXCEPTION = 19

    def __str__(self) -> str:
        return self.name.lower().replace('_', ' ')


class Event:
    def __init__(self, text: str, tg_message_unix_date: datetime, event_id: int) -> None:
        self.id = event_id
        self.match_id = None
        self.status = EVENT_STATUS.NEW
        self.desc = None
        self.date_last_try = '0000-00-00_00-00-00'
        self.processing_time = None
        self.date_bet_accept = None
        self.time_event_start = None
        self.date_message_send = tg_message_unix_date
        self.date_added = datetime.now().strftime(DATE_FORMAT)
        self.__parse_text(text)
        self.max_bet_amount = []
        self.coupon_coeff = None
        self.history_coeff = []
        logging.info(f'Put event in queue: {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}')
        print(f'Put event in queue: {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}')

    def __parse_text(self, text: str) -> None:
        self.sport = text[:text.find(';')]                                      # Футбол; League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
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
        self.__parse_teams()
        text = text[text.find(':') + 2:]                                        # O(1)=1.57;
        self.__parse_type(text)
        if self.type_text == 'total' or self.type_text == 'handicap':
            self.__parse_market()
        self.coeff = float(text[text.find('=') + 1:text.find(';')])             # O(1)=1.57;

    def __parse_teams(self) -> None:
        if self.sport == 'Теннис':
            self.teams = self.team1
        elif self.sport in ['Футбол', 'Хоккей']:
            self.teams = self.team1 + ' - ' + self.team2
        else:
            self.teams = ''
            self.status = EVENT_STATUS.SPORT_NOT_DEFINED

    def __parse_type(self, text: str) -> None:  # text = 'O(1)=1.57'
        self.type = text[:text.find('=')]
        if self.type[0] == 'W':  # W1 / W2
            self.type_text = 'winner'
            self.winner_team = int(self.type[1])
        elif (self.type[0] == '1' or self.type[0] == '2') and len(self.type) == 1:  # 1 / 2
            self.type_text = 'winner'
            self.type = 'W' + self.type[0]
            self.winner_team = int(self.type[1])
        elif self.type[:2] == '1X':  # 1X
            self.type_text = 'win_or_draw'
            self.winner_team = 1
        elif self.type[:2] == 'X2':  # X2
            self.type_text = 'win_or_draw'
            self.winner_team = 2
        elif self.type[0] == 'U':  # U(?.??)
            self.type_text = 'total'
            self.winner_team = 1
        elif self.type[0] == 'O':  # O(?.??)
            self.type_text = 'total'
            self.winner_team = 2
        elif self.type[:2] == 'AH':  # AH1(?.??) / AH2(?.??)
            self.type_text = 'handicap'
            if self.type[2] == '1' or self.type[2] == '2':
                self.winner_team = int(self.type[2])
            else:
                self.type_text = ''
                self.status = EVENT_STATUS.TYPE_NOT_DEFINED
                return
        else:
            self.type_text = ''
            self.status = EVENT_STATUS.TYPE_NOT_DEFINED
            return
        print(self.type_text)

    def __parse_market(self) -> None:
        try:
            market_value = float(self.type[self.type.find('(') + 1:self.type.find(')')])
        except ValueError:
            self.status = EVENT_STATUS.TYPE_NOT_DEFINED
            return
        if market_value * 100 % 50 == 0:  # обычный тотал или обычная фора
            if self.type_text == 'total':
                self.market_str = collect_total_str('simple', market_value)
                self.markets_table_name = 'Тотал голов'
            elif self.type_text == 'handicap':
                self.market_str = collect_handicap_str('simple', market_value)
                self.markets_table_name = 'Победа с учетом форы'
        else:  # иной тотал или иная фора
            if self.type_text == 'total':
                self.market_str = collect_total_str('asia', market_value)
                self.markets_table_name = 'Азиатский тотал голов'
            elif self.type_text == 'handicap':
                self.market_str = collect_handicap_str('asia', market_value)
                self.markets_table_name = 'Победа с учетом азиатской форы'
        if self.market_str is None:
            self.market_str = ''
            self.status = EVENT_STATUS.CANT_CONSTRUCT_STRING
        if self.markets_table_name is None:
            self.markets_table_name = ''
            self.status = EVENT_STATUS.CANT_CONSTRUCT_STRING
        if self.status == EVENT_STATUS.CANT_CONSTRUCT_STRING:
            return
        logging.info(f'event.market_str is {self.market_str.translate(tr)}')
        print(f'event.market_str is {self.market_str.translate(tr)}')
        logging.info(f'event.markets_table_name is {self.markets_table_name.translate(tr)}')
        print(f'event.markets_table_name is {self.markets_table_name.translate(tr)}')

    def __str__(self) -> str:
        return self.__dict__.__str__()

    def __repr__(self) -> str:
        return self.__dict__

    def to_json(self) -> dict:
        # logging.info(f"obj dict is {self.id} | {self.team1_eng} | {self.team2_eng} | {self.type} | {self.coeff}")
        json_dict = {}
        for key, value in self.__dict__.items():
            json_dict[key] = value
            if isinstance(self.__dict__[key], EVENT_STATUS):
                json_dict[key] = str(value)
        return json_dict
