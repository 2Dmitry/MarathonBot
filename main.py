import json
import logging
import multiprocessing
import os
import shutil
# import smtplib
import time
from datetime import datetime
from multiprocessing import Process, Queue
from random import randint

import telebot
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from src.event import EVENT_STATUS, Event
from src.page_elements import *
from src.utils import get_driver, logger_info_wrapper


# TODO BUG:  функциях/классах не должно быть логов и принтов, вытащить их в мэин
# BUG: переделать/добавить тотал/гандикап в азиатский_тотал/гандикап, а то везде используется просто тотал и дополнительная лишняя проверка на название таблицы рынков
# BUG: лучше не отправлять два события одновременно
# BUG: бот не работает если свернута кнопка купона P.S. знаю, обычно она не свернута

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
MASTERS = ['milovdd@mail.ru', 'pozdnyakov.aleksey.m@gmail.com', 'panamanagolve@gmail.com']
# ==============================</EMAIL>=============================

os.makedirs(LOGS_PATH, exist_ok=True)
os.makedirs(BETS_PATH, exist_ok=True)

logging.basicConfig(filename=LOGS_PATH + "/{}.log".format(datetime.now().strftime(DATE_FORMAT)),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)
# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.debug('Start')

try:
    with open('config.json', encoding=ENCODING) as f:
        CONFIG_JSON = json.load(f)
        logging.info('Config file open')
except FileNotFoundError as ex:
    logging.exception('Config file not found')
    logging.exception(str(ex))
    raise ex


# ==================<Телеграм бот>=====================================================
# инициализировать строго после чтения конфиг файла
TELEGRAM_BOT = telebot.TeleBot(CONFIG_JSON['token'])
# ==================</Телеграм бот>=====================================================


@logger_info_wrapper
def move_bets_history() -> dict:
    """читаем историю ставок, если файл найден, значит у бота есть стартовая инфа"""
    event_dict = {}
    try:
        with open('bets.json', encoding=ENCODING) as f:
            event_dict = json.load(f)
            logging.info('Bets history file open')
            shutil.move('bets.json', BETS_PATH + '/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
    except FileNotFoundError:
        logging.info('Bets history file not found')

    finally:
        return event_dict


def convert_date_into_seconds(text):
    # 08-08-2021_09-11-54
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


@logger_info_wrapper
def update_config_file():  # TODO delete: not use
    with open('config.json', 'w', encoding=ENCODING) as f:
        json.dump(CONFIG_JSON, f, indent=1)


@logger_info_wrapper
def log_in_marathonbet_account(webdriver_mar, email_message_queue):
    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        logging.info('log_in: Exit button found: no need to login')
        logging.info('log_in: stop')
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(CONFIG_JSON['username'])
        logging.info('log_in: Username entered')
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(CONFIG_JSON['password'])
    logging.info('log_in: Password entered')
    time.sleep(1)

    sign_in_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    sign_in_button.click()
    logging.info('log_in: "Sign in" button found and click')
    time.sleep(2)

    # не всегда просит капчу, не просит видимо тогда, когда с данного устройства (ВДС) и с данного IP уже заходили в данную учетку
    # TODO здесь добавить решение гугл-капчи
    logging.info('log_in: Google reCaptcha solved')

    try:
        notification_text = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, 'messenger.hidden.simplemodal-data'))).text
        if notification_text.find('Ваш счёт закрыт') != -1:
            logging.info('log_in: your account is closed')
            time.sleep(60)
            return
    except TimeoutException:
        pass

    while True:
        try:
            wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
            logging.info('log_in: Google reCaptcha solved')
            time.sleep(5)
            return
        except TimeoutException:
            email_message_queue.put_nowait(f'log_in: {datetime.now().strftime(DATE_FORMAT)}')
            logging.info(f'log_in: {datetime.now().strftime(DATE_FORMAT)}')
            time.sleep(5)
            pass


@logger_info_wrapper
def close_bk_message(webdriver_mar) -> None:
    """
        закрытие уведомления от букмекера
    """
    wait_2 = WebDriverWait(webdriver_mar, 2)

    try:
        message_close_button = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, CLOSE_BK_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        logging.info('close_bk_message: No message from a bookmaker')
        return

    message_close_button.click()
    logging.info('close_bk_message: Close message button found and click')
    return


@logger_info_wrapper
def close_promo_message(webdriver_mar) -> None:
    """
        закрытие рекламного уведомления от букмекера
    """
    wait_2 = WebDriverWait(webdriver_mar, 2)

    try:
        message_close_button = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, CLOSE_PROMO_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        logging.info('close_promo_message: No promo message from a bookmaker')
        return
    message_close_button.click()
    logging.info('close_promo_message: Close promo message button found and click')
    return


@logger_info_wrapper
def search_event_by_teams(webdriver_mar, event: Event):
    wait_5 = WebDriverWait(webdriver_mar, 5)

    search_icon_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
    search_icon_button.click()
    logging.info('search_event_by_teams: Search icon button found and click')
    time.sleep(3)

    search_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(event.teams)
    logging.info('search_event_by_teams: Search field found and click, event_name enter')
    time.sleep(3)

    search_enter_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    logging.info('search_event_by_teams: Search enter button found and click')
    time.sleep(3)

    try:
        search_sport_tab_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException:
        event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        event.status = EVENT_STATUS.NO_SEARCH_RESULTS
        logging.info('search_event_by_teams: Cannot click on the button (search_sport_tab_button) because no events were found')
        logging.info('search_event_by_teams: stop')
        # TODO ну тут надо сделать уведомление, что ниче не найдено
        return event
    search_sport_tab_button.click()
    logging.info('search_event_by_teams: Search sports tab button found and click')
    time.sleep(2)
    return event


@logger_info_wrapper
def show_more_markets_or_do_nothing(webdriver_mar):
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        event_more_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, EVENT_MORE_BUTTON_CLASS)))
        event_more_button.click()
    except TimeoutException:  # штатная ситуация, означает что линия "узкая"
        logging.info('show_more_markets_or_do_nothing: Event more button not found')
        logging.info('show_more_markets_or_do_nothing: stop')
        return False
    logging.info('show_more_markets_or_do_nothing: Event more button found and click')
    time.sleep(1)

    all_markets_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, 'active-shortcut-menu-link')))
    all_markets_button.click()
    logging.info('show_more_markets_or_do_nothing: Event more button found and click')
    time.sleep(1)
    return True


@logger_info_wrapper
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
                        logging.info('get_market_table_by_name: found and click on shortcut menu')
                        time.sleep(2)
                break

    markets_list = []
    for table in webdriver_mar.find_elements_by_class_name('market-inline-block-table-wrapper'):
        for market_table_name in table.find_elements_by_class_name('market-table-name'):
            if market_table_name.text == markets_table_name:
                for market in table.find_elements_by_tag_name('td'):
                    markets_list.append(market)
                logging.info('get_market_table_by_name: got table with markets')
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

    logging.info('get_main_market_table: dont got table with markets')
    return


@logger_info_wrapper
def find_market_in_the_main_bar(main_bar, event: Event):
    market = None

    if event.sport == 'Теннис':
        if event.type_text == 'winner':  # победа команды 1 / победа команды 2
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[0]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[1]

    elif event.sport == 'Футбол' or event.sport == 'Хоккей':
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
        # общий тотал  # TODO быдлокод
        elif event.type_text == 'total' and event.markets_table_name != 'Азиатский тотал голов':
            if event.winner_team == 1:  # победа команды 1
                market = main_bar[8]
            elif event.winner_team == 2:  # победа команды 2
                market = main_bar[9]
        # общая фора  # TODO быдлокод
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


@logger_info_wrapper
def check_coupon_coeff(event, webdriver_mar):
    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
    event.status = 'Coupon coeff will be updated in coupon'
    try:
        coupon_delete_all = wait_2.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
        coupon_delete_all.click()
    except TimeoutException:
        pass

    time.sleep(1)
    webdriver_mar.refresh()
    time.sleep(2)
    try:
        search_sport_tab_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException:
        event.status = EVENT_STATUS.NO_SEARCH_RESULTS  # не найдено ни одного матча соответствующего поиску
        event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        logging.info('check_coupon_coeff: Cannot click on the button (search_sport_tab_button) because no events were found')
        # TODO ну тут надо сделать уведомление, что ниче не найдено, т.к. это странно, если событие пришло, значит что-то должно быть найдено, иначе ошибка в парсере
        logging.info('check_coupon_coeff: stop')
        return event
    search_sport_tab_button.click()
    logging.info('check_coupon_coeff: Search sports tab button found and click')
    time.sleep(2)
    return event


@logger_info_wrapper
def change_language(webdriver_mar):
    wait_2 = WebDriverWait(webdriver_mar, 2)

    lang_settings_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]')))
    lang_settings_button.click()
    logging.info('change_language: found and click change language button')
    time.sleep(1)

    close_bk_message(webdriver_mar)
    close_promo_message(webdriver_mar)

    languages_rus_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]/div[2]/div/div[2]/span[6]/span[2]')))
    languages_rus_button.click()
    logging.info('change_language: found and click change russian language button')
    time.sleep(1)


@logger_info_wrapper
def controller(proc_marathon_bot, proc_message_to_mail):  # TODO dont work
    proc_status = {'browser_bot_run': False, 'mail_bot_run': False,
                   'browser_bot_stop': False, 'mail_bot_stop': False}
    PROC_STATUS_QUELIST.put_nowait(proc_status)
    while True:
        proc_status = PROC_STATUS_QUELIST.get()
        if proc_status['browser_bot_run']:
            if not proc_marathon_bot.is_alive():
                proc_marathon_bot = Process(target=start_marathon_bot, name='start_marathon_bot', args=(EVENTS_QUEUE, EMAIL_MESSAGE_QUEUE,))
                proc_marathon_bot.start()
            proc_status['browser_bot_run'] = False

        if proc_status['browser_bot_stop']:
            proc_marathon_bot.terminate()
            proc_status['browser_bot_stop'] = False

        if proc_status['mail_bot_stop']:
            proc_message_to_mail.terminate()
            proc_status['mail_bot_stop'] = False

        PROC_STATUS_QUELIST.put_nowait(proc_status)
        time.sleep(2)


@logger_info_wrapper
@TELEGRAM_BOT.message_handler(content_types=['text'])
def get_text_TGmessages(message):
    if message.text == 'bot id':
        TELEGRAM_BOT.send_message(message.chat.id, CONFIG_JSON["bot_id"])

    elif ';' in message.text:  # если пришло именно событие в сообщении, значит после вида спорта должна обязательно стоять ";"
        event = Event(message.text, message.date, CONFIG_JSON['event_id'])
        CONFIG_JSON['event_id'] += 1
        update_config_file()
        EVENTS_QUEUE.put_nowait(event)
        logging.info('Put event in QUEUE')
        TELEGRAM_BOT.send_message(message.chat.id, f'bot{CONFIG_JSON["bot_id"]} получил событие')

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
        TELEGRAM_BOT.send_message(message.chat.id, f'bot{CONFIG_JSON["bot_id"]} вас не понимает')


def start_marathon_bot(events_queue, email_message_queue):
    webdriver_mar = get_driver('/GoogleChrome', CONFIG_JSON['username'])

    wait_1 = WebDriverWait(webdriver_mar, 1)
    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    webdriver_mar.get(CONFIG_JSON['marathon_mirror'])
    logging.info("Marathon's page is open")

    log_in_marathonbet_account(webdriver_mar, email_message_queue)
    webdriver_mar.refresh()
    time.sleep(10)

    close_bk_message(webdriver_mar)
    close_promo_message(webdriver_mar)
    close_bk_message(webdriver_mar)

    if not CONFIG_JSON['ru']:
        change_language(webdriver_mar)

    webdriver_mar.refresh()
    time.sleep(3)

    move_bets_history()
    events_dict = {}
    # TODO в очередь положить события, которые могут быть еще "сыграны"

    date_now = None
    event = None
    while True:
        if event is not None:
            if event.status == EVENT_STATUS.BET_ACCEPTED:
                event.processing_time = convert_date_into_seconds(event.date_last_try) - date_now
            key = event.team1 + ' - ' + event.team2 + ' - ' + str(event.date_message_send)
            events_dict[key] = event.to_json()
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

            if event.status == EVENT_STATUS.TYPE_NOT_DEFINED:
                continue

            if event.status == EVENT_STATUS.SPORT_NOT_DEFINED:
                continue

            if event.status == EVENT_STATUS.CANT_CONSTRUCT_STRING:
                continue

            logging.info(f'Browser get event from queue: {event.id} | {event.team1_eng} | {event.team2_eng} | {event.type} | {event.coeff}')
            date_now = convert_date_into_seconds(datetime.now().strftime(DATE_FORMAT))
            diff_sec = date_now - convert_date_into_seconds(event.date_last_try)
            if event.time_event_start is not None:
                diff_sec2 = convert_start_time_match_into_seconds(event.time_event_start) - date_now
            else:
                diff_sec2 = convert_start_time_match_into_seconds('23:59') - date_now
            if event.date_last_try != '0000-00-00_00-00-00':
                if (diff_sec < CONFIG_JSON["freq_update_sec"]) and (diff_sec2 > CONFIG_JSON['time_before_the_start']):
                    # событие будет возвращено в очередь,
                    # так как freq_update_sec еще не прошло с момента последней попытки И
                    # И времени до начала события больше чем time_before_the_start
                    event.desc = 'insufficient time difference, pls wait'
                    events_queue.put_nowait(event)
                    logging.info(f'{diff_sec}<{CONFIG_JSON["freq_update_sec"]} and {diff_sec2}>{CONFIG_JSON["time_before_the_start"]} = TRUE. Event put back')
                    time.sleep(2)
                    continue
                if diff_sec > CONFIG_JSON["freq_update_sec"]:
                    logging.info('Event coeff will be updated')
                if diff_sec2 < CONFIG_JSON['time_before_the_start'] and event.desc != 'Event soon started':
                    event.desc = 'Event soon started'
                    logging.info('Event soon started')
                elif date_now > convert_start_time_match_into_seconds(event.time_event_start):
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.desc = EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN
                    event.status = EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN
                    logging.info(EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN)
                    print(EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN)
                    continue
            print(f'Browser get event from queue: {event.id} | {event.team1_eng} | {event.team2_eng} | {event.type} | {event.coeff}')
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.IN_PROGRESS

        rnd = randint(0, 10)
        logging.info(f'sleep {rnd} sec')
        print(f'sleep {rnd} sec')
        time.sleep(rnd)

        event = search_event_by_teams(webdriver_mar, event)

        if event.status == EVENT_STATUS.NO_SEARCH_RESULTS:
            continue

        if event.id is None:
            try:
                event_id = webdriver_mar.find_element_by_class_name(CATEGORY_CLASS).get_attribute('href')
            except NoSuchElementException:
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN
                logging.info(EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN)
                print(EVENT_STATUS.EVENT_HAS_ALREADY_BEGUN)
                continue
            event.id = event_id[event_id.find('+-+') + 3:]

        if event.time_event_start is None:
            try:
                event.time_event_start = webdriver_mar.find_element_by_class_name('date.date-short').text
            except NoSuchElementException:
                event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                event.status = EVENT_STATUS.NO_SEARCH_RESULTS
                logging.info(EVENT_STATUS.NO_SEARCH_RESULTS)
                print(EVENT_STATUS.NO_SEARCH_RESULTS)
                continue

        markets_list = []
        coupon_coeff = None
        need_to_check_main_market_bar = True
        need_to_check_big_market_bar = False
        while True:
            if event.status == EVENT_STATUS.NO_SEARCH_RESULTS:  # TODO это тупо (1)
                break

            try:
                coupon_delete_all = wait_1.until(ec.element_to_be_clickable((By.CLASS_NAME, 'button.btn-remove')))
                coupon_delete_all.click()
                time.sleep(1)
                logging.info('Coupon cleared')
            except TimeoutException:
                logging.info('Coupon is empty')
                pass

            if need_to_check_main_market_bar:
                market = find_market_in_the_main_bar(get_main_market_table(webdriver_mar), event)
                if market is not None:
                    try:
                        if market.text == '—':
                            logging.info('market.text is "—"')
                            need_to_check_main_market_bar = True
                            need_to_check_big_market_bar = True
                            event.status = EVENT_STATUS.COEFFICIENT_DOES_NOT_EXIST_IN_MARKET
                            logging.info(EVENT_STATUS.COEFFICIENT_DOES_NOT_EXIST_IN_MARKET)
                            print(EVENT_STATUS.COEFFICIENT_DOES_NOT_EXIST_IN_MARKET)
                            break
                        elif event.type_text == 'winner' or event.type_text == 'win_or_draw':
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
                            need_to_check_main_market_bar = False
                            need_to_check_big_market_bar = True
                            event.status = EVENT_STATUS.MARKET_NOT_FOUND
                            logging.info(f'{EVENT_STATUS.MARKET_NOT_FOUND} in the main market bar')
                            print(f'{EVENT_STATUS.MARKET_NOT_FOUND} in the main market bar')
                    except ElementNotInteractableException:
                        continue
                else:
                    need_to_check_main_market_bar = False
                    need_to_check_big_market_bar = True

            if need_to_check_big_market_bar:
                if not show_more_markets_or_do_nothing(webdriver_mar):
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_NOT_FOUND
                    logging.info(EVENT_STATUS.MARKET_NOT_FOUND)
                    print(EVENT_STATUS.MARKET_NOT_FOUND)
                    logging.info('Put event in QUEUE')
                    events_queue.put_nowait(event)
                    break
                markets_list.extend(get_markets_table_by_name(webdriver_mar, event.markets_table_name))
                if len(markets_list) == 0:  # входит в if в том случае, если не найдена таблица с рынками, например таблицы с Тоталами нет в принципе
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_TABLE_NOT_FOUND
                    logging.info(EVENT_STATUS.MARKET_TABLE_NOT_FOUND)
                    print(EVENT_STATUS.MARKET_TABLE_NOT_FOUND)
                    logging.info('Put event in QUEUE')
                    events_queue.put_nowait(event)
                    break
                winner_team_markets = sort_market_table_by_teamnum(markets_list, event.winner_team)
                while len(winner_team_markets) != 0:
                    market = winner_team_markets.pop()
                    if market.text.find(event.market_str) != -1:
                        market.click()
                        logging.info(f'Market found and click: {market.text}')
                        time.sleep(1)
                        break
                else:
                    event.date_last_try = datetime.now().strftime(DATE_FORMAT)
                    event.status = EVENT_STATUS.MARKET_NOT_FOUND
                    logging.info(f'{EVENT_STATUS.MARKET_NOT_FOUND} in the big bar')
                    print(f'{EVENT_STATUS.MARKET_NOT_FOUND} in the big bar')
                    events_queue.put_nowait(event)
                    logging.info('Put event in QUEUE')
                    break

            coupon_coeff = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, 'choice-price')))  # BUG находит кэф только первого исхода в купоне (по идее)
            try:
                coupon_coeff = float(coupon_coeff.text[coupon_coeff.text.find(':') + 2:])
            except ValueError:  # коэффициент обновился уже будучи в купоне
                logging.info('Coupon coeff has been updated in coupon')
                event = check_coupon_coeff(event, webdriver_mar)  # TODO это тупо (1)
                continue
            event.coupon_coeff = coupon_coeff
            event.history_coeff.append(datetime.now().strftime('%H:%M:%S'))
            event.history_coeff.append(coupon_coeff)
            break

        if event.status == EVENT_STATUS.COEFFICIENT_DOES_NOT_EXIST_IN_MARKET:
            continue

        if event.status == EVENT_STATUS.MARKET_NOT_FOUND:
            continue

        if event.status == EVENT_STATUS.MARKET_TABLE_NOT_FOUND:
            continue

        if event.status == EVENT_STATUS.NO_SEARCH_RESULTS:  # TODO это тупо (1)
            continue

        max_bet_amount = None
        try:
            max_bet_amount = webdriver_mar.find_element_by_xpath('/html/body/div[11]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/div[1]/div[2]/table/tbody/tr/td[2]/div[2]/span[1]').text
            max_bet_amount = max_bet_amount.replace(',', '')
            max_bet_amount = float(max_bet_amount)
            event.max_bet_amount.append(datetime.now().strftime('%H:%M:%S'))
            event.max_bet_amount.append(max_bet_amount)
            logging.info(f'max bet amount is {max_bet_amount}')
            print(f'max bet amount is {max_bet_amount}')
        except Exception as ex:
            logging.info(ex)
            print(ex)

        if max_bet_amount is not None and max_bet_amount < CONFIG_JSON['bet_mount_rub']:
            webdriver_mar.refresh()
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.CUT
            logging.info(EVENT_STATUS.CUT)
            print(EVENT_STATUS.CUT)
            rnd = randint(5, 10)
            logging.info(f'sleep {rnd} sec')
            print(f'sleep {rnd} sec')
            time.sleep(rnd)
            continue

        if (event.coeff - 0.2) > event.coupon_coeff:
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            logging.info(f'Event.coeff is {event.coeff}. Coupon coeff is {event.coupon_coeff}. {event.coeff - 0.2} > {event.coupon_coeff}')
            print(f'Event.coeff is {event.coeff}. Coupon coeff is {event.coupon_coeff}. {event.coeff - 0.2} > {event.coupon_coeff}')
            event.status = EVENT_STATUS.NOT_TRY_COUPON_COEFF
            print(EVENT_STATUS.NOT_TRY_COUPON_COEFF)
            logging.info('Put event in QUEUE')
            events_queue.put_nowait(event)
            continue

        try:
            wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        except TimeoutException:
            email_message_queue.put_nowait(f'you are logged out, date: {datetime.now().strftime(DATE_FORMAT)}')
            logging.info(f'you are logged out, date: {datetime.now().strftime(DATE_FORMAT)}')
            webdriver_mar.refresh()
            event.coupon_coeff = coupon_coeff
            event.date_bet_accept = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.FAKE_BET_ACCEPTED
            event.desc = 'you are logged out'
            logging.info(EVENT_STATUS.FAKE_BET_ACCEPTED)
            print(EVENT_STATUS.FAKE_BET_ACCEPTED)
            rnd = randint(2, 10)
            logging.info(f'sleep {rnd} sec')
            print(f'sleep {rnd} sec')
            time.sleep(rnd)
            continue
        logging.info('you are logged in')

        # try:
        stake_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, STAKE_FIELD_CLASS)))  # в купоне вбиваем сумму ставки
        stake_field.clear()
        stake_field.send_keys(CONFIG_JSON['bet_mount_rub'])
        time.sleep(1)
        logging.info(f'Stake field found and bet amount ({CONFIG_JSON["bet_mount_rub"]}) entered')
        # except Exception as ex:  # быдлокод
        #     event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        #     event.status = 'Cant print bet mount in stake field'
        #     logging.info('Cant print bet mount in stake field')
        #     logging.info('Put event in QUEUE')
        #     events_queue.put_nowait(event)
        #     logging.info(str(ex))
        #     continue

        # try:
        stake_accept_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, STAKE_ACCEPT_BUTTON_XPATH)))  # "принять" ставку
        stake_accept_button.click()
        time.sleep(2)
        logging.info('Accept button found and click')
        # except Exception as ex:  # быдлокод
        #     event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        #     event.status = 'Cant click accept button'
        #     logging.info('Cant click accept button')
        #     logging.info('Put event in QUEUE')
        #     events_queue.put_nowait(event)
        #     logging.info(str(ex))
        #     continue

        # try:
        notification_text = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, 'messenger.hidden.simplemodal-data'))).text
        # except Exception as ex:  # быдлокод
        #     event.date_last_try = datetime.now().strftime(DATE_FORMAT)
        #     event.status = 'wtf'
        #     print('wtf')
        #     logging.info('wtf')
        #     logging.info('Put event in QUEUE')
        #     events_queue.put_nowait(event)
        #     logging.info(str(ex))
        #     time.sleep(600)
        #     continue
        if notification_text.find('Пари принято') != -1:  # на eu версии сайта возможно другое уведомление
            webdriver_mar.refresh()
            event.date_bet_accept = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.BET_ACCEPTED
            logging.info(EVENT_STATUS.BET_ACCEPTED)
            print(EVENT_STATUS.BET_ACCEPTED)
            rnd = randint(2, 10)
            logging.info(f'sleep {rnd} sec')
            print(f'sleep {rnd} sec')
            time.sleep(rnd)
            continue
        elif notification_text.find('Повторная ставка в пари') != -1:  # на eu версии сайта возможно другое уведомление
            webdriver_mar.refresh()
            event.date_last_try = datetime.now().strftime(DATE_FORMAT)
            event.status = EVENT_STATUS.RE_BET
            logging.info(EVENT_STATUS.RE_BET)
            print(EVENT_STATUS.RE_BET)
            logging.info('Put event in QUEUE')
            events_queue.put_nowait(event)
            rnd = randint(5, 10)
            logging.info(f'sleep {rnd} sec')
            print(f'sleep {rnd} sec')
            time.sleep(rnd)
            continue


def main():
    proc_marathon_bot = Process(target=start_marathon_bot, name='start_marathon_bot', args=(EVENTS_QUEUE, EMAIL_MESSAGE_QUEUE,))
    proc_marathon_bot.start()
    TELEGRAM_BOT.polling(none_stop=True, interval=1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
