import json
import logging
import multiprocessing
import os
import shutil
import smtplib
import time
from datetime import datetime
from multiprocessing import Process, Queue

import telebot
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from src.event import EVENT_STATUS, Event
from src.utils import get_driver

# from telebot import types  # Подключаем библиотеку для создания кнопок


# ==============================<Глобальные переменные>==============================
EVENTS_QUEUE = Queue()
EMAIL_MESSAGE_QUEUE = Queue()
PROC_STATUS_QUELIST = Queue()
ENCODING = 'utf-8'
BETS_PATH = 'workdir/bets'
LOGS_PATH = 'workdir/logs'
DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'
MAIN_CHAT_ID = -1001541447697
MYSELF_CHAT_ID = 477446257
# ==============================</Глобальные переменные>=============================


# ==============================<EMAIL>=============================
# SMTP_OBJ = smtplib.SMTP('smtp.mail.ru', 587)
# SMTP_OBJ.starttls()
# SMTP_OBJ.login('marathon_bet_bots@bk.ru', 'UPEjoz8xJbrjsM3v45Fz')
MASTERS = ['milovdd@mail.ru', 'pozdnyakov.aleksey.m@gmail.com',
           'panamanagolve@gmail.com']
# ==============================</EMAIL>=============================

# ==================<Кнопки и поля, которые есть в бк MarathonBet>===================
EXIT_BUTTON_CLASS = 'marathon_icons-exit_icon'
USERNAME_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__input'
PASSWORD_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__password'
SIGN_IN_BUTTON_CLASS = 'form__element.auth-form__submit.auth-form__enter.green'
CLOSE_BK_MESSAGE_BUTTON_CLASS = 'button.btn-cancel.no.simplemodal-close'
CLOSE_PROMO_MESSAGE_BUTTON_CLASS = 'v-icon.notranslate.prevent-page-leave-modal-button.v-icon--link.v-icon--auto-fill'
SEARCH_ICON_BUTTON_CLASS = 'search-widget_button--toggle.main'
SEARCH_ICON_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/button'
SEARCH_FIELD_CLASS = 'search-widget_input'
SEARCH_ENTER_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/div/div[1]/div/button[1]'
SEARCH_SPORTS_TAB_BUTTON_XPATH = '//*[@id="search-result-container"]/div[1]/div/button[3]/span'
EVENT_MORE_BUTTON_CLASS = 'event-more-view'
STAKE_FIELD_CLASS = 'stake.stake-input.js-focusable'
STAKE_ACCEPT_BUTTON_XPATH = '//*[@id="betslip_placebet_btn_id"]'
CATEGORY_CLASS = 'category-label-link'
ALL_MARKETS_BUTTON_FPATH = '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/div[2]/div/div[1]/table/tbody/tr[1]/td[1]'
# ==================</Кнопки и поля, которые есть в бк MarathonBet>=================



# event = {'status': EVENT_STATUS.NEW,
#              'id': None,
#              'date_message_send': tg_message_unixdate,
#              'date_added': datetime.now().strftime(DATE_FORMAT),
#              'date_bet_accept': None,
#              'date_last_try': '0000-00-00_00-00-00',
#              'time_event_start': None,
#              'processing_time': None,
#              'desc': None,
#              'sport': text[:text.find(';')]}

os.makedirs(LOGS_PATH, exist_ok=True)  # создаем необходимые папки
os.makedirs(BETS_PATH, exist_ok=True)  # создаем необходимые папки

logging.basicConfig(filename=LOGS_PATH + "/{}.log".format(datetime.now().strftime(DATE_FORMAT)),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)
# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(
    logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.debug('Start')

try:  # читаем конфиг файл  # TODO завернуть это в функцию
    with open('config.json', encoding=ENCODING) as f:
        CONFIG_JSON = json.load(f)
        logging.info('Config file open')
except FileNotFoundError as e:
    logging.exception('Config file not found')
    logging.exception(str(e))
    raise e


# ==================<Телеграм бот>=====================================================
# инициализировать строго после чтения конфиг файла
TELEGRAM_BOT = telebot.TeleBot(CONFIG_JSON['token'])
# ==================</Телеграм бот>=====================================================

def move_bets_history():
    """читаем историю ставок, если файл найден, значит у бота есть стартовая инфа"""
    event_dict = {}
    try:
        with open('bets.json', encoding=ENCODING) as f:
            event_dict = json.load(f)
            logging.info('Bets history file open')
    except FileNotFoundError:
        logging.info('Bets history file not found')
        return event_dict

    shutil.move('bets.json', BETS_PATH +
                '/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
    return event_dict


def convert_date_into_seconds(text):  # 08-08-2021_09-11-54
    text = text[text.find('-') + 1:]  # 08-2021_09-11-54
    text = text[text.find('-') + 1:]  # 2021_09-11-54
    text = text[text.find('_') + 1:]  # 09-11-54
    hours = text[:text.find('-')]  # 09
    text = text[text.find('-') + 1:]  # 11-54
    minutes = int(text[:text.find('-')]) * 60  # 11
    seconds = int(text[text.find('-') + 1:])  # 54
    if hours == '00' and minutes == 0 and seconds == 0:
        return 0
    elif hours == '00':  # если событие начинается "завтра", то 00 часов это 24 часа
        hours = '24'
    hours = int(hours) * 3600
    summ_seconds = hours + minutes + seconds
    return summ_seconds


def convert_start_time_match_into_seconds(text):
    if ' ' in text:  # если дата это строка такого рода: "1 авг 02:00"
        return 24 * 3600  # типа событие в 23:59 начинается
    hours = text[:text.find(':')]
    if hours == '00':
        return 24 * 3600  # типа событие в 23:59 начинается
    hours = int(hours)
    text = text[text.find(':') + 1:]
    minutes = int(text)
    summ_seconds = hours * 3600 + minutes * 60
    return summ_seconds


def parse_TGmessage_with_event(text: str, tg_message_unixdate: datetime):
    event = Event(text, tg_message_unixdate)
    # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
    text = text[text.find(';') + 2:]
    # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
    event.league = text[text.find(':') + 2:text.find(';')]
    text = text[text.find(';') + 2:]  # Ранхейм vs Фредрикстад: O(1)=1.57;
    # Ранхейм vs Фредрикстад: O(1)=1.57;
    event.team1 = text[:text.find(' vs ')]
    # Ранхейм vs Фредрикстад: O(1)=1.57;
    event.team2 = text[text.find(' vs ') + 4:text.find(':')]
    text = text[text.find(':') + 2:]  # O(1)=1.57;
    event.type = text[:text.find('=')]  # O(1)=1.57;
    event.markets_table_name = None
    event.winner_team = None
    event.market_str = None
    event.coeff = float(
        text[text.find('=') + 1:text.find(';')])  # O(1)=1.57;
    event.coupon_coeff = None
    event.history_coeff = []
    logging.info(f'Bot takes event: {event.date_message_send}')
    print(event)
    print('\n')
    return event


def update_config_file():  # TODO delete: not use
    with open('config.json', 'w', encoding=ENCODING) as f:
        json.dump(CONFIG_JSON, f, indent=1)
        logging.info('Config file saved')


def log_in_marathonbet_account(webdriver_mar, email_message_queue):
    logging.info('login: start')

    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        wait_2.until(ec.element_to_be_clickable(
            (By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        logging.info('login: Exit button found: no need to login')
        logging.info('login: stop')
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable(
            (By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(CONFIG_JSON['username'])
        logging.info('login: Username entered')
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable(
        (By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(CONFIG_JSON['password'])
    logging.info('login: Password entered')
    time.sleep(1)

    sign_in_button = wait_5.until(ec.element_to_be_clickable(
        (By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    sign_in_button.click()
    logging.info('login: "Sign in" button found and click')
    time.sleep(2)

    # не всегда просит капчу, не просит видимо тогда, когда с данного устройства (ВДС) и с данного IP уже заходили в данную учетку
    # TODO здесь добавить решение гугл-капчи
    # logging.info('login: Google reCaptcha solved')

    while True:
        try:
            wait_2.until(ec.element_to_be_clickable(
                (By.CLASS_NAME, EXIT_BUTTON_CLASS)))
            logging.info('login: Google reCaptcha solved')
            logging.info('login: stop')
            time.sleep(5)
            return
        except TimeoutException:
            if True:  # TODO
                msg = f'd{datetime.now().strftime(DATE_FORMAT)} - Google captcha. I can not log in to your account for more than 3 minutes.'
                email_message_queue.put_nowait(msg)
                logging.info(
                    f'd{datetime.now().strftime(DATE_FORMAT)} - Google captcha. I can not log in to your account for more than 3 minutes.')
            pass


def close_bk_message(webdriver_mar):
    logging.info('close_bk_message: start')
    wait_2 = WebDriverWait(webdriver_mar, 2)

    try:
        message_close_button = wait_2.until(ec.element_to_be_clickable(
            (By.CLASS_NAME, CLOSE_BK_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        # сообщений/уведомлений от букера нет, закрывать окно не надо
        logging.info('close_bk_message: No message from a bookmaker')
        # TODO может ли быть два окна подряд? хз..хз...
        logging.info('close_bk_message: stop')
        return
    
    message_close_button.click()
    logging.info('close_bk_message: Close message button found and click')
    logging.info('close_bk_message: stop')


def close_promo_message(webdriver_mar):
    logging.info('close_promo_message: start')
    wait_2 = WebDriverWait(webdriver_mar, 2)

    try:
        message_close_button = wait_2.until(
            ec.element_to_be_clickable((By.CLASS_NAME, CLOSE_PROMO_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        logging.info(
            'close_promo_message: No promo message from a bookmaker')  # сообщений/уведомлений от букера нет, закрывать окно не надо
        # TODO может ли быть два окна подряд? хз..хз...
        logging.info('close_promo_message: stop')
        return
    message_close_button.click()
    logging.info(
        'close_promo_message: Close promo message button found and click')
    logging.info('close_promo_message: stop')


def search_event_by_teams(webdriver_mar, event):
    logging.info('search_event_by_teams: start')
    wait_5 = WebDriverWait(webdriver_mar, 5)

    if event.sport == 'Теннис':  # найти собыйтие через поисковую строку, переключиться на вкладку "Спорт"  # TODO запихнуть это в if который ниже отвечает за поиск маркета
        teams = event.team1
    elif event.sport == 'Футбол' or event.sport == 'Хоккей':
        teams = event.team1 + ' - ' + event.team2
    else:  # событие не надо обратно класть в очередь, оно уже было удалено из очереди,
        # надо просто изменить значение его полей и при заходе на новый цикл информация в файле bets будет обновлена
        logging.info('Event sport not defined')
        event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        event.status = EVENT_STATUS.SPORT_NOT_DEFINED
        return False

    search_icon_button = wait_5.until(
        ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
    search_icon_button.click()
    logging.info('search_event_by_teams: Search icon button found and click')
    time.sleep(3)

    search_field = wait_5.until(ec.element_to_be_clickable(
        (By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(teams)
    logging.info(
        'search_event_by_teams: Search field found and click, event_name enter')
    time.sleep(3)

    search_enter_button = wait_5.until(
        ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    logging.info('search_event_by_teams: Search enter button found and click')
    time.sleep(3)

    try:
        search_sport_tab_button = wait_5.until(
            ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException:
        event.status = EVENT_STATUS.NO_SEARCH_RESULTS
        # не найдено ни одного матча соответствующего поиску
        logging.info(
            'search_event_by_teams: Cannot click on the button (search_sport_tab_button) because no events were found')
        # TODO ну тут надо сделать уведомление, что ниче не найдено
        logging.info('search_event_by_teams: stop')
        return False
    search_sport_tab_button.click()
    logging.info(
        'search_event_by_teams: Search sports tab button found and click')
    time.sleep(2)

    logging.info('search_event_by_teams: stop')
    return True


def show_more_markets_or_do_nothing(webdriver_mar):
    logging.info('show_more_markets_or_do_nothing: start')
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        event_more_button = wait_5.until(ec.element_to_be_clickable(
            (By.CLASS_NAME, EVENT_MORE_BUTTON_CLASS)))
        event_more_button.click()
    except TimeoutException:  # штатная ситуация, означает что линия "узкая"
        logging.info(
            'show_more_markets_or_do_nothing: Event more button not found')
        logging.info('show_more_markets_or_do_nothing: stop')
        return
    logging.info(
        'show_more_markets_or_do_nothing: Event more button found and click')
    time.sleep(1)

    all_markets_button = wait_5.until(ec.element_to_be_clickable(
        (By.CLASS_NAME, 'active-shortcut-menu-link')))
    all_markets_button.click()
    logging.info(
        'show_more_markets_or_do_nothing: Event more button found and click')
    time.sleep(1)
    logging.info('show_more_markets_or_do_nothing: stop')


def get_markets_table_by_name(webdriver_mar, markets_table_name):
    shortcut_name = 'Все выборы'
    if markets_table_name is not None:
        if markets_table_name.find('Тотал голов') != -1 or markets_table_name.find('Азиатский тотал голов') != -1:
            shortcut_name = 'Тоталы'
        elif markets_table_name.find('Победа с учетом форы') != -1 or markets_table_name.find('Победа с учетом азиатской форы') != -1:
            shortcut_name = 'Форы'

    for table in webdriver_mar.find_elements_by_tag_name('table'):
        if table.get_attribute('class') == 'table-shortcuts-menu':
            for shortcut_menu_row in table.find_elements_by_tag_name('tr'):
                for element_from_shortcut_menu_row in shortcut_menu_row.find_elements_by_tag_name('td'):
                    if element_from_shortcut_menu_row.text.find(shortcut_name) != -1:
                        element_from_shortcut_menu_row.click()
                        logging.info(
                            'get_market_table_by_name: found and click on shortcut menu')
                        time.sleep(2)
                break

    markets_list = []
    for table in webdriver_mar.find_elements_by_class_name('market-inline-block-table-wrapper'):
        for market_table_name in table.find_elements_by_class_name('market-table-name'):
            if market_table_name.text == markets_table_name:
                for market in table.find_elements_by_tag_name('td'):
                    markets_list.append(market)
                logging.info(
                    'get_market_table_by_name: got table with markets')
                return markets_list

    logging.info('get_market_table_by_name: cant get table with markets')
    return markets_list


def get_main_market_table(webdriver_mar):
    table_lst = []
    for table in webdriver_mar.find_elements_by_tag_name('table'):
        if table.get_attribute('class') == 'coupon-row-item':
            for table_once_tr in table.find_elements_by_tag_name('tr'):
                for table_once_tr_td in table_once_tr.find_elements_by_tag_name('td'):
                    if 'price' in table_once_tr_td.get_attribute('class'):
                        table_lst.append(table_once_tr_td)
            logging.info('get_main_market_table: got table with markets')
            return table_lst

    logging.info('get_main_market_table: got table with markets')
    return


def find_market_in_the_main_bar(main_bar, evnt, winner, total, handicap, win_or_draw):
    market = None
    if evnt['sport'] == 'Теннис':
        if winner:  # победа команды 1 / победа команды 2
            if evnt['winner_team'] == 1:  # победа команды 1
                market = main_bar[0]
            elif evnt['winner_team'] == 2:  # победа команды 2
                market = main_bar[1]
    elif evnt['sport'] == 'Футбол' or evnt['sport'] == 'Хоккей':
        if winner:  # победа команды 1 / победа команды 2
            if evnt['winner_team'] == 1:  # победа команды 1
                market = main_bar[0]
            elif evnt['winner_team'] == 2:  # победа команды 2
                market = main_bar[2]
        elif win_or_draw:  # 1X / X2
            if evnt['winner_team'] == 1:  # 1X
                market = main_bar[3]
            elif evnt['winner_team'] == 2:  # X2
                market = main_bar[5]
        # общий тотал  # TODO быдлокод
        elif total and evnt['markets_table_name'] != 'Азиатский тотал голов':
            if evnt['winner_team'] == 1:  # победа команды 1
                market = main_bar[8]
            elif evnt['winner_team'] == 2:  # победа команды 2
                market = main_bar[9]
        # общая фора  # TODO быдлокод
        elif handicap and evnt['markets_table_name'] != 'Победа с учетом азиатской форы':
            if evnt['winner_team'] == 1:  # победа команды 1
                market = main_bar[6]
            elif evnt['winner_team'] == 2:  # победа команды 2
                market = main_bar[7]
    return market


def sort_market_table_by_teamnum(lst, team_num):
    logging.info('sort_market_table_by_teamnumb: start')
    team_num = int(team_num)
    new_lst = []
    if team_num == 1:
        for i in range(0, len(lst), 2):
            new_lst.append(lst[i])
    if team_num == 2:
        for i in range(1, len(lst), 2):
            new_lst.append(lst[i])
    logging.info(
        'sort_market_table_by_teamnumb: create new list (teams/under/over). stop')
    return new_lst


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
    logging.info('collect_handicap_str: collect handicap string')
    return text


def collect_total_str(text, total_value):
    if text == 'asia':
        text = f'({total_value - 0.25},{total_value + 0.25})'
    elif text == 'simple':  # тотала 0 не бывает, минимум 0.5 и только положительный
        text = f'({total_value})'
    logging.info('collect_total_str: collect total string')
    return text


def change_language(webdriver_mar):
    wait_2 = WebDriverWait(webdriver_mar, 2)
    logging.info('change_language: start')

    lang_settings_button = wait_2.until(
        ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]')))
    lang_settings_button.click()
    logging.info('change_language: found and click change language button')
    time.sleep(1)

    close_bk_message(webdriver_mar)
    close_promo_message(webdriver_mar)

    languages_rus_button = wait_2.until(ec.element_to_be_clickable(
        (By.XPATH, '//*[@id="language_form"]/div[2]/div/div[2]/span[6]/span[2]')))
    languages_rus_button.click()
    logging.info(
        'change_language: found and click change russian language button')
    time.sleep(1)

    logging.info('change_language: stop')


def start_marathon_bot(events_queue, email_message_queue):
    webdriver_mar = get_driver('/GoogleChrome', CONFIG_JSON['username'])
    logging.info('Browser is open')

    wait_1 = WebDriverWait(webdriver_mar, 1)
    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    webdriver_mar.get(CONFIG_JSON['marathon_mirror'])
    logging.info("Marathon's page is open")

    log_in_marathonbet_account(
        webdriver_mar, email_message_queue)  # вход в аккаунт
    webdriver_mar.refresh()
    time.sleep(3)

    close_bk_message(webdriver_mar)  # закрытие уведомления от букмекера
    # закрытие рекламного уведомления от букмекера
    close_promo_message(webdriver_mar)

    change_language(webdriver_mar)  # сменить язык на русский
    webdriver_mar.refresh()
    time.sleep(3)

    move_bets_history()
    events_dict = {}
    # TODO в очередь положить события, которые могут быть еще "сыграны"

    datenow = None
    event = None
    while True:
        if event is not None:
            if event.status == EVENT_STATUS.STATUS_BET_ACCEPTED:
                event.processing_time = convert_date_into_seconds(
                    event.date_last_try) - datenow
            key = event.team1 + ' - ' + event.team2 + \
                ' - ' + str(event.date_message_send)
            events_dict[key] = event
            with open('bets.json', 'w', encoding=ENCODING) as f:
                json.dump(events_dict, f, indent=1, ensure_ascii=False)
            logging.info('bets.json updated')
            event = None

        if events_queue.empty():
            # TODO добавить каждые 30 минут клики в "пустоту"
            logging.info('QUEUE is empty')
            time.sleep(2)
            continue
        else:
            event = events_queue.get()
            logging.info(
                f'Get event {event.date_message_send} from QUEUE, coeff: {event.coeff}')
            datenow = convert_date_into_seconds(
                datetime.now().strftime(DATE_FORMAT))
            diff_sec = datenow - \
                convert_date_into_seconds(event.date_last_try)
            if event.time_event_start is not None:
                diff_sec2 = convert_start_time_match_into_seconds(
                    event.time_event_start) - datenow
            else:
                diff_sec2 = convert_start_time_match_into_seconds(
                    '23:59') - datenow
            if event.date_last_try != '0000-00-00_00-00-00':
                if (diff_sec < CONFIG_JSON["freq_update_sec"]) and (diff_sec2 > CONFIG_JSON['time_before_the_start']):
                    # событие будет возвращено в очередь,
                    # так как freq_update_sec еще не прошло с момента последней попытки И
                    # времени до начала события больше чем time_before_the_start
                    event.desc = 'insufficient time difference, pls wait'
                    events_queue.put_nowait(event)
                    logging.info(
                        f'{diff_sec}<{CONFIG_JSON["freq_update_sec"]} and {diff_sec2}>{CONFIG_JSON["time_before_the_start"]} = TRUE. Event put back')
                    time.sleep(2)
                    continue
                if diff_sec > CONFIG_JSON["freq_update_sec"]:
                    event.desc = 'Event coeff will be updated'
                    logging.info('Event coeff will be updated')
                if diff_sec2 < CONFIG_JSON['time_before_the_start'] and event.desc != 'Event soon started':
                    event.desc = 'Event soon started'
                    logging.info('Event soon started')
                # TODO delete это возможно не нужно, понаблюдать
                elif datenow > convert_start_time_match_into_seconds(event.time_event_start):
                    event.desc = 'Event has already begun'
                    logging.info('No bet. Event has already begun')
                    continue
            event.status = EVENT_STATUS.IN_PROGRESS

        winner = False
        total = False
        handicap = False
        win_or_draw = False
        if event.winner_team is None:
            if event.type[0] == 'W':  # W1 / W2
                winner = True
                event.winner_team = int(event.type[1])
            elif (event.type[0] == '1' or event.type[0] == '2') and len(event.type) == 1:  # 1 / 2
                winner = True
                event.type = 'W' + event.type[0]
                event.winner_team = int(event.type[1])
            elif event.type[:2] == '1X':  # 1X
                win_or_draw = True
                event.winner_team = 1
            elif event.type[:2] == 'X2':  # X2
                win_or_draw = True
                event.winner_team = 2
            elif event.type[0] == 'U':  # U(?.??)
                total = True
                event.winner_team = 1
            elif event.type[0] == 'O':  # O(?.??)
                total = True
                event.winner_team = 2
            elif event.type[:2] == 'AH':  # AH1(?.??) / AH2(?.??)
                handicap = True
                if event.type[2] == '1' or event.type[2] == '2':
                    event.winner_team = int(event.type[2])
                else:
                    logging.info('Event handicap type not defined')
                    # TODO писать сообщение в конфу, что тип события не определен
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.TYPE_NOT_DEFINED
                    continue
            else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                logging.info('Event type not defined')
                # TODO писать сообщение в конфу, что тип события не определен
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = EVENT_STATUS.TYPE_NOT_DEFINED
                continue

        if not search_event_by_teams(webdriver_mar, event):
            continue

        if event.id is None:
            try:
                event_id = webdriver_mar.find_element_by_class_name(
                    CATEGORY_CLASS).get_attribute('href')
            except NoSuchElementException as e:  # если событие не найдено через строку поиска, то перейти к следующему
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = 'Event isnot on the Sports tab'
                logging.info('Event isnot on the Sports tab')
                logging.info(str(e))
                continue
            event.id = event_id[event_id.find('+-+') + 3:]

        if event.time_event_start is None:
            try:
                event.time_event_start = webdriver_mar.find_element_by_class_name(
                    'date.date-short').text
            except NoSuchElementException as e:  # если событие не найдено через строку поиска, то перейти к следующему
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = EVENT_STATUS.NO_SEARCH_RESULTS
                logging.info(EVENT_STATUS.NO_SEARCH_RESULTS)
                logging.info(str(e))
                continue

        markets_list = []
        markets_table_name = None
        market_str = None
        if total or handicap:
            try:
                market_value = float(
                    event.type[event.type.find('(') + 1:event.type.find(')')])
            except ValueError:
                logging.info('Event type not defined')
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = EVENT_STATUS.TYPE_NOT_DEFINED
                continue

            if event.market_str is None and event.markets_table_name is None:
                if market_value * 100 % 50 == 0:  # обычный тотал или фора
                    if total:
                        market_str = collect_total_str('simple', market_value)
                        markets_table_name = 'Тотал голов'
                    elif handicap:
                        market_str = collect_handicap_str(
                            'simple', market_value)
                        markets_table_name = 'Победа с учетом форы'
                else:
                    if total:
                        market_str = collect_total_str('asia', market_value)
                        markets_table_name = 'Азиатский тотал голов'
                    elif handicap:
                        market_str = collect_handicap_str('asia', market_value)
                        markets_table_name = 'Победа с учетом азиатской форы'
                event.market_str = market_str
                event.markets_table_name = markets_table_name
            if market_str is None:
                logging.info('cant convert event type into market_str')
                event.desc = 'cant convert event type into market_str'
                continue
            if markets_table_name is None:
                logging.info('cant set markets_table_name')
                event.desc = 'cant set markets_table_name'
                continue

        coupon_coeff = 0
        need_to_check_main_market_bar = True
        need_to_check_big_market_bar = False
        while True:
            # если в купоне есть событие(-ия), то купон будет очищен (теоретически в купоне не может быть больше чем 1 маркета)
            try:
                # '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span'
                coupon_delete_all = wait_1.until(
                    ec.element_to_be_clickable((By.CLASS_NAME, 'button.btn-remove')))
                coupon_delete_all.click()
                time.sleep(1)
                logging.info('Coupon cleared')
            except TimeoutException:
                logging.info('Coupon is empty')
                pass

            if need_to_check_main_market_bar:
                market = find_market_in_the_main_bar(get_main_market_table(
                    webdriver_mar), event, winner, total, handicap, win_or_draw)
                if market is not None:
                    if market.text == '—':
                        logging.info('market.text is "—"')
                        need_to_check_main_market_bar = True
                        need_to_check_big_market_bar = True
                        break
                    elif winner or win_or_draw:
                        # эквивалентно event.market_str = Null
                        market.click()
                        logging.info(f'Market found and click: {market.text}')
                        time.sleep(1)
                        need_to_check_main_market_bar = True
                        need_to_check_big_market_bar = False
                    elif market.text.find(event.market_str) != -1:
                        market.click()
                        logging.info(f'Market found and click: {market.text}')
                        time.sleep(1)
                        need_to_check_main_market_bar = True
                        need_to_check_big_market_bar = False
                    else:
                        need_to_check_big_market_bar = True
                        logging.info('not foundnd market str in market')
                else:
                    need_to_check_main_market_bar = False
                    need_to_check_big_market_bar = True

            if need_to_check_big_market_bar:
                show_more_markets_or_do_nothing(webdriver_mar)
                markets_list.extend(get_markets_table_by_name(
                    webdriver_mar, event.markets_table_name))
                if len(markets_list) == 0:  # TODO быдлокод
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_NOT_FOUND
                    events_queue.put_nowait(event)
                    logging.info('Put event in QUEUE')
                    logging.info('Market not found')
                    break
                winner_team_markets = sort_market_table_by_teamnum(
                    markets_list, event.winner_team)
                if len(winner_team_markets) == 0:  # TODO быдлокод
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_NOT_FOUND
                    events_queue.put_nowait(event)
                    logging.info('Put event in QUEUE')
                    logging.info(
                        'Market not found. len(winner_team_markets)  is 0')
                    break
                while len(winner_team_markets) != 0:  # TODO быдлокод
                    market = winner_team_markets.pop()
                    if market.text.find(event.market_str) != -1:
                        market.click()
                        bl = True
                        logging.info(f'Market found and click: {market.text}')
                        time.sleep(1)
                        break
                else:
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_NOT_FOUND
                    events_queue.put_nowait(event)
                    logging.info('Put event in QUEUE')
                    logging.info('Not found market in the big bar')
                    break
                if bl is not None and bl:
                    break

            if event.status == EVENT_STATUS.MARKET_NOT_FOUND:
                logging.info('ALARM WTF')
                break

            # ищем значение коэф-та в купоне P.S. не работает с двумя и более выборами в одном купоне
            try:
                coupon_coeff = wait_2.until(
                    ec.element_to_be_clickable((By.CLASS_NAME, 'choice-price')))
            except TimeoutException:  # TODO я правда хз как вызвать это исключение
                logging.info('ALARM! Dont know what is it')
                webdriver_mar.refresh()
                logging.info('Refresh page')
                time.sleep(2)
                continue
            try:
                coupon_coeff = float(
                    coupon_coeff.text[coupon_coeff.text.find(':') + 2:])
            except ValueError:  # TODO это исключение срабатывает в том случае, если коэффициент обновился уже будучи в купоне. НАДО: очистить купон, нажать на кэф снова.
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = 'Coupon coeff will be updated in coupon'
                coupon_delete_all = wait_1.until(ec.element_to_be_clickable(
                    (By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
                coupon_delete_all.click()
                time.sleep(1)
                logging.info('Coupon coeff will be updated in coupon')
                webdriver_mar.refresh()
                time.sleep(2)
                try:
                    search_sport_tab_button = wait_5.until(
                        ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
                except TimeoutException:
                    event.status = EVENT_STATUS.NO_SEARCH_RESULTS
                    # не найдено ни одного матча соответствующего поиску
                    logging.info(
                        'search_event_by_teams: Cannot click on the button (search_sport_tab_button) because no events were found')
                    # TODO ну тут надо сделать уведомление, что ниче не найдено
                    logging.info('search_event_by_teams: stop')
                    return False
                search_sport_tab_button.click()
                logging.info(
                    'search_event_by_teams: Search sports tab button found and click')
                time.sleep(2)
                continue

            # event.history_coeff.append(datetime.now().strftime('%H:%M:%S'))
            # event.history_coeff.append(coupon_coeff)
            # event.coupon_coeff = coupon_coeff
            # event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            # event.status = 'Found coupon coeff'
            break

        if event.status == EVENT_STATUS.MARKET_NOT_FOUND:
            continue

        if (event.coeff - 0.2) > coupon_coeff:
            # коэффициент в купоне не удовлетворяет условиям, событие будет отправлено в конец очереди
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.NOT_TRY_COUPON_COEFF
            event.coupon_coeff = coupon_coeff
            event.history_coeff.append(datetime.now().strftime('%H:%M:%S'))
            event.history_coeff.append(coupon_coeff)
            events_queue.put_nowait(event)
            logging.info('Not try coupon coeff')
            logging.info('Put event in QUEUE')
            continue
        # if (event.coeff * (100 - COEFF_DIFF_PERCENTAGE)/100) > coupon_coeff:  # запасной код на случай если понадобится сделать проценты
        #     logging.info(f"NOT TRY coeff: {coupon_coeff} event_coeff: {event.coeff}")
        #     continue

        try:
            stake_field = wait_5.until(ec.element_to_be_clickable(
                (By.CLASS_NAME, STAKE_FIELD_CLASS)))  # в купоне вбиваем сумму ставки
            stake_field.clear()
            stake_field.send_keys(CONFIG_JSON['bet_mount_rub'])
            time.sleep(1)
            logging.info('Stake field found and bet amount entered')
        except Exception as e:  # вернул событие в очередь, может быть не надо?
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = 'Cant print bet mount in stake field'
            events_queue.put_nowait(event)
            logging.info('Cant print bet mount in stake field')
            logging.info('Put event in QUEUE')
            logging.info(str(e))
            continue

        try:
            stake_accept_button = wait_5.until(ec.element_to_be_clickable(
                (By.XPATH, STAKE_ACCEPT_BUTTON_XPATH)))  # "принять" ставку
            stake_accept_button.click()
            time.sleep(2)
            logging.info('Accept button found and click')
        except Exception as e:  # вернул событие в очередь, может быть не надо?
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = 'Cant click accept button'
            events_queue.put_nowait(event)
            logging.info('Cant click accept button')
            logging.info('Put event in QUEUE')
            logging.info(str(e))
            continue

        webdriver_mar.refresh()
        event.coupon_coeff = coupon_coeff
        event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        event.date_bet_accept= datetime.now().strftime(DATE_FORMAT)
        event.status = EVENT_STATUS.BET_ACCEPTED
        logging.info('Bet accepted')
        # TODO время ожидания после совершения ставки, сделать "рандомное" время на основе какого-нибудь закона
        time.sleep(5)


def controller(proc_marathon_bot, proc_message_to_mail):  # TODO dont work
    proc_status = {'browser_bot_run': False, 'mail_bot_run': False,
                   'browser_bot_stop': False, 'mail_bot_stop': False}
    PROC_STATUS_QUELIST.put_nowait(proc_status)
    while True:
        proc_status = PROC_STATUS_QUELIST.get()
        if proc_status['browser_bot_run']:
            if not proc_marathon_bot.is_alive():
                proc_marathon_bot = Process(target=start_marathon_bot, name='start_marathon_bot', args=(
                    EVENTS_QUEUE, EMAIL_MESSAGE_QUEUE,))
                proc_marathon_bot.start()
            proc_status['browser_bot_run'] = False
        # if proc_status['mail_bot_run']:
        #     if not proc_marathon_bot.is_alive():
        #         proc_message_to_mail = Process(target=send_message_to_mail, name='send_message_to_mail', args=(EMAIL_MESSAGE_QUEUE,))
        #         proc_message_to_mail.start()
        #     proc_status['mail_bot_run'] = False
        if proc_status['browser_bot_stop']:
            proc_marathon_bot.terminate()
            proc_status['browser_bot_stop'] = False
        if proc_status['mail_bot_stop']:
            proc_message_to_mail.terminate()
            proc_status['mail_bot_stop'] = False
        PROC_STATUS_QUELIST.put_nowait(proc_status)
        time.sleep(2)


@TELEGRAM_BOT.message_handler(content_types=['text'])
def get_text_TGmessages(message):
    if message.text == 'bot id':
        TELEGRAM_BOT.send_message(message.chat.id, CONFIG_JSON["bot_id"])
    elif ';' in message.text:  # если пришло именно событие в сообщении, значит после вида спорта должна обязательно стоять ";"
        event = parse_TGmessage_with_event(message.text, message.date)
        EVENTS_QUEUE.put_nowait(event)
        logging.info('Put event in QUEUE')
        TELEGRAM_BOT.send_message(
            message.chat.id, f'bot{CONFIG_JSON["bot_id"]} получил событие')
    elif message.text == 'start' or message.text == f'bot{CONFIG_JSON["bot_id"]} start':
        qwerty = PROC_STATUS_QUELIST.get()
        qwerty['browser_bot_run'] = True
        qwerty['mail_bot_run'] = True
        PROC_STATUS_QUELIST.put(qwerty)
    elif message.text == 'stop browser' or message.text == f'bot{CONFIG_JSON["bot_id"]} stop browser':
        qwerty = PROC_STATUS_QUELIST.get()
        qwerty['browser_bot_stop'] = True
        PROC_STATUS_QUELIST.put(qwerty)
    elif message.text == 'stop email' or message.text == f'bot{CONFIG_JSON["bot_id"]} stop email':
        qwerty = PROC_STATUS_QUELIST.get()
        qwerty['mail_bot_stop'] = True
        PROC_STATUS_QUELIST.put(qwerty)
    else:
        TELEGRAM_BOT.send_message(
            message.chat.id, f'bot{CONFIG_JSON["bot_id"]} вас не понимает')


def main():
    proc_marathon_bot = Process(target=start_marathon_bot, name='start_marathon_bot', args=(
        EVENTS_QUEUE, EMAIL_MESSAGE_QUEUE,))
    proc_marathon_bot.start()
    # proc_message_to_mail = Process(target=send_message_to_mail, name='send_message_to_mail', args=(EMAIL_MESSAGE_QUEUE,))
    # proc_message_to_mail.start()
    # Process(target=controller, name='controller', args=(proc_marathon_bot, proc_message_to_mail,)).start()
    # Process(target=botbot, name='botbot', args=()).start()
    # TODO не получилось передать в процесс очередь, поэтому делать тупо через полинг в мэйне
    TELEGRAM_BOT.polling(none_stop=True, interval=1)


if __name__ == "__main__":  # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        print(str(e))
        EMAIL_MESSAGE_QUEUE.put_nowait(str(e))
        logging.exception(str(e))
        raise e
