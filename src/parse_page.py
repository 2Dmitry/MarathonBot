import time
import logging
from random import randint

from src.event import Event
from src.utils import logger_info_wrapper
from selenium.webdriver.common.by import By

SYMBOLS = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
           u"abvgdeejzijklmnoprstufhzcss_y'euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y'EUA")
tr = {ord(a): ord(b) for a, b in zip(*SYMBOLS)}

@logger_info_wrapper
def get_markets_table_by_name(webdriver_mar, markets_table_name):
    shortcut_name = 'Все выборы'
    if markets_table_name is not None:
        if markets_table_name.find('Тотал голов') != -1 or markets_table_name.find('Азиатский тотал голов') != -1:
            shortcut_name = 'Тоталы'
        elif markets_table_name.find('Победа с учетом форы') != -1 or markets_table_name.find('Победа с учетом азиатской форы') != -1:
            shortcut_name = 'Форы'
    # logging.info(f'get_market_table_by_name: shortcut_name is {shortcut_name.translate(tr)}')
    # print(f'get_market_table_by_name: shortcut_name is {shortcut_name.translate(tr)}')

    for table in webdriver_mar.find_elements(By.CLASS_NAME, 'table-shortcuts-menu'):
        for element_from_shortcut_menu_row in table.find_elements(By.TAG_NAME, 'td'):
            if element_from_shortcut_menu_row.text.find(shortcut_name) != -1:
                element_from_shortcut_menu_row.click()
                logging.info('get_market_table_by_name: found and click on shortcut menu')
                time.sleep(randint(17, 27) / 10)
                break

    # for table in webdriver_mar.find_elements(By.TAG_NAME, 'table'):
    #     if table.get_attribute('class') == 'table-shortcuts-menu':
    #         for shortcut_menu_row in table.find_elements(By.TAG_NAME, 'tr'):
    #             for element_from_shortcut_menu_row in shortcut_menu_row.find_elements(By.TAG_NAME, 'td'):
    #                 if element_from_shortcut_menu_row.text.find(shortcut_name) != -1:
    #                     element_from_shortcut_menu_row.click()
    #                     logging.info('get_market_table_by_name: found and click on shortcut menu')
    #                     time.sleep(randint(17, 27)/10)
    #             break

    markets_list = []
    for table in webdriver_mar.find_elements(By.CLASS_NAME, 'market-inline-block-table-wrapper'):
        for market_table_name in table.find_elements(By.CLASS_NAME, 'market-table-name'):
            if market_table_name.text.find(markets_table_name) != -1:
                for market in table.find_elements(By.TAG_NAME, 'td'):
                    markets_list.append(market)
                logging.info('get_market_table_by_name: got table with markets')
                return markets_list

    logging.info('get_market_table_by_name: cant get table with markets')
    return markets_list


@logger_info_wrapper
def get_main_market_table(webdriver_mar):
    table_lst = []
    for table in webdriver_mar.find_elements(By.CLASS_NAME, 'coupon-row-item'):
        for market in table.find_elements(By.TAG_NAME, 'td'):
            if 'price' in market.get_attribute('class'):
                table_lst.append(market)

    logging.info('get_main_market_table: got main table')
    print(len(table_lst))
    return table_lst

    # for table in webdriver_mar.find_elements(By.TAG_NAME, 'table'):
    #     if table.get_attribute('class') == 'coupon-row-item':
    #         for table_once_tr in table.find_elements(By.TAG_NAME, 'tr'):
    #             for table_once_tr_td in table_once_tr.find_elements(By.TAG_NAME, 'td'):
    #                 if 'price' in table_once_tr_td.get_attribute('class'):
    #                     table_lst.append(table_once_tr_td)
    #         logging.info('get_main_market_table: got main table')
    #         return table_lst


@logger_info_wrapper
def find_market_in_the_main_bar(main_bar, event: Event):
    market = None

    if event.sport == 'Теннис':
        if event.type_text == 'winner':  # победа команды 1 / победа команды 2
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[0]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[1]

    elif event.sport in ['Футбол', 'Хоккей']:
        if event.type_text == 'winner':  # победа команды 1 / победа команды 2
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[0]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[2]
        elif event.type_text == 'win_or_draw':  # 1X / X2
            if event.winner_team == 1:  # 1X
                market = main_bar[3]
            elif event.winner_team == 2:  # X2
                market = main_bar[5]
        elif event.type_text == 'total' and event.markets_table_name != 'Азиатский тотал голов':
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[8]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[9]
        elif event.type_text == 'handicap' and event.markets_table_name != 'Победа с учетом азиатской форы':
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[6]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[7]
    return market


@logger_info_wrapper
def sort_market_table_by_teamnum(lst, team_num):
    team_num = int(team_num)
    new_lst = []
    if team_num == 1:
        for i in range(0, len(lst), 2):
            new_lst.append(lst[i])
    if team_num == 2:
        for i in range(1, len(lst), 2):
            new_lst.append(lst[i])
    return new_lst