import time
from datetime import datetime
import json
import os
import shutil
import multiprocessing
from multiprocessing import Process, Queue
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, \
    StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from src.utils import get_driver
import logging
import telebot  # Подключаем Telegram API
#from telebot import types  # Подключаем библиотеку для создания кнопок


#==============================<Глобальные переменные>==============================
EVENTS_QUEUE = Queue()
ENCODING = 'utf-8'
BETS_PATH = 'workdir/bets'
LOGS_PATH = 'workdir/logs'
#==============================</Глобальные переменные>=============================




os.makedirs(LOGS_PATH, exist_ok=True)  # создаем необходимые папки
os.makedirs(BETS_PATH, exist_ok=True)  # создаем необходимые папки

logging.basicConfig(filename=LOGS_PATH+"/{}.log".format(datetime.now().strftime('%d-%m-%Y_%H-%M-%S')),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)
# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.CRITICAL)
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




#==================<Телеграм бот>=====================================================
TELEGRAM_BOT = telebot.TeleBot(CONFIG_JSON['token'])  # инициализировать строго после чтения конфиг файла
#==================</Телеграм бот>=====================================================


#==============================<Event status>=======================================
STATUS_NEW = 'New'
STATUS_IN_PROGRESS = 'In progress'
STATUS_NO_SEARCH_RESULTS = 'No search results'
STATUS_TYPE_NOT_DEFINED = "Event's type not defined"
STATUS_SPORT_NOT_DEFINED = "Event's sport not defined"
STATUS_MARKET_NOT_FOUND = 'Market not found'
STATUS_NOT_TRY_COUPON_COEFF = 'Not try coupon coeff'
# TODO добавить статус "Не удалось считать кэф из купона"
STATUS_BET_ACCEPTED = 'Bet accepted'
#==============================</Event status>======================================


#==================<Кнопки и поля, которые есть в бк MarathonBet>===================
EXIT_BUTTON_CLASS = 'marathon_icons-exit_icon'
USERNAME_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__input'
PASSWORD_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__password'
SIGN_IN_BUTTON_CLASS = 'form__element.auth-form__submit.auth-form__enter.green'
CLOSE_BK_MESSAGE_BUTTON_CLASS = 'button.btn-cancel.no.simplemodal-close'
CLOSE_PROMO_MESSAGE_BUTTON_CLASS = 'v-icon.notranslate.prevent-page-leave-modal-button.v-icon--link.v-icon--auto-fill'
SEARCH_ICON_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/button'
SEARCH_FIELD_CLASS = 'search-widget_input'
SEARCH_ENTER_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/div/div[1]/div/button[1]'
SEARCH_SPORTS_TAB_BUTTON_XPATH = '//*[@id="search-result-container"]/div[1]/div/button[3]/span'
EVENT_MORE_BUTTON_CLASS = 'event-more-view'
STAKE_FIELD_CLASS = 'stake.stake-input.js-focusable'
STAKE_ACCEPT_BUTTON_XPATH = '//*[@id="betslip_placebet_btn_id"]'
CATEGORY_CLASS = 'category-label-link'
ALL_MARKETS_BUTTON_FPATH = '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/div[2]/div/div[1]/table/tbody/tr[1]/td[1]'
SOCCER_WINNER1_BUTTON_FPATH = '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[3]'
SOCCER_WINNER2_BUTTON_FPATH = '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[5]'
TENNIS_WINNER1_BUTTON_FPATH = '//*[@id="category11981449"]/div/div/div[2]/table/tbody/tr/td[3]'
TENNIS_WINNER2_BUTTON_FPATH = '//*[@id="category11981449"]/div/div/div[2]/table/tbody/tr/td[4]'
# TODO добавить кнопки, которые встречаются по коду, в глобальные переменные
# TODO сделать несколько кнопок, которые могут отвечать, например за победу1 в теннисе, за победу1 в футболе
#==================</Кнопки и поля, которые есть в бк MarathonBet>=================


def move_bets_history(dict):  # читаем историю ставок, если файл найден, значит у бота есть стартовая инфа
    try:
        with open('bets.json', encoding=ENCODING) as f:
            dict = json.load(f)
            logging.info('Bets history file open')
    except FileNotFoundError:
        logging.info('Bets history file not found')
        return dict

    shutil.move('bets.json', BETS_PATH+'/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
    return dict


def convert_date_into_seconds(text):                                     # 08-08-2021_09-11-54
    text = text[text.find('-') + 1:]                        # 08-2021_09-11-54
    text = text[text.find('-') + 1:]                        # 2021_09-11-54
    text = text[text.find('_') + 1:]                        # 09-11-54
    hours = text[:text.find('-')]                            # 09
    text = text[text.find('-') + 1:]                        # 11-54
    minutes = int(text[:text.find('-')]) * 60               # 11
    seconds = int(text[text.find('-') + 1:])                # 54
    if hours == '00' and minutes == 0 and seconds == 0:
        return 0;
    elif hours == '00':                                        # если событие начинается "завтра", то 00 часов это 24 часа
        hours = '24'
    hours = int(hours) * 3600
    summ_seconds = hours + minutes + seconds
    return summ_seconds


def convert_start_time_match_into_seconds(text):
    if ' ' in text:  # если дата это строка такого рода: "1 авг 02:00"
        # text = text[text.find(' ') + 1:]  # "авг 02:00"
        # text = text[text.find(' ') + 1:]  # "02:00"
        return 24 * 3600  # типа событие в 23:59 начинается
    hours = text[:text.find(':')]
    if hours == '00':
        return 24 * 3600  # типа событие в 23:59 начинается
    hours = int(hours)
    text = text[text.find(':')+1:]
    minutes = int(text)
    summ_seconds = hours * 3600 + minutes * 60
    return summ_seconds


def parse_TGmessage_with_event(text, tg_message_unixdate):
    event = {}                                                          # 0123456789@0123456789@0123456789@0123456789@0123456789@0123456789@012
    event['status'] = STATUS_NEW
    event['id'] = None
    event['date_message_send'] = tg_message_unixdate
    event['date_added'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
    event['date_last_try'] = '00-00-0000_00-00-00'
    event['time_event_start'] = None
    event['processing_time'] = None
    event['desc'] = None
    event['sport'] = text[:text.find(';')]                              # Футбол; League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
    text = text[text.find(';') + 2:]                                    # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
    event['league'] = text[text.find(':') + 2:text.find(';')]           # League: Norway - League 1; Ранхейм vs Фредрикстад: O(1)=1.57;
    text = text[text.find(';') + 2:]                                    # Ранхейм vs Фредрикстад: O(1)=1.57;
    event['team1'] = text[:text.find(' vs ')]                           # Ранхейм vs Фредрикстад: O(1)=1.57;
    event['team2'] = text[text.find(' vs ') + 4:text.find(':')]         # Ранхейм vs Фредрикстад: O(1)=1.57;
    text = text[text.find(':') + 2:]                                    # O(1)=1.57;
    event['type'] = text[:text.find('=')]                               # O(1)=1.57;
    event['coeff'] = float(text[text.find('=') + 1:text.find(';')])     # O(1)=1.57;
    event['coupon_coeff'] = None
    logging.info(f'Bot takes event: {event["date_message_send"]}')
    return event



def update_config_file():  # TODO delete: not use
    with open('config.json', 'w', encoding=ENCODING) as f:
        json.dump(CONFIG_JSON, f, indent=1)
        logging.info('Config file saved')


@TELEGRAM_BOT.message_handler(content_types=['text'])
def get_text_TGmessages(message):
    if message.text == 'bot id':
        TELEGRAM_BOT.send_message(message.chat.id, CONFIG_JSON["bot_id"])
    elif message.text == (f'bot{CONFIG_JSON["bot_id"]} привет'):
        TELEGRAM_BOT.send_message(message.chat.id, f'bot{CONFIG_JSON["bot_id"]} говорит: "Привет <3"')
    elif ';' in message.text:  # если пришло именно событие в сообщении, значит после вида спорта должна обязательно стоять ";"
        event = parse_TGmessage_with_event(message.text, message.date)
        EVENTS_QUEUE.put_nowait(event)
        logging.info('Put event in QUEUE')
        TELEGRAM_BOT.send_message(message.chat.id, f'bot{CONFIG_JSON["bot_id"]} получил событие')
    elif message.text == 'stop':
        pass  # TODO придумать что-нибудь
    else:
        TELEGRAM_BOT.send_message(message.chat.id, f'bot{CONFIG_JSON["bot_id"]} вас не понимает')


def log_in_marathonbet_account(webdriver_mar):
    logging.info('login: start')

    wait_2 = WebDriverWait(webdriver_mar, 2)
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        logging.info('login: Exit button found: no need to login')
        logging.info('login: stop')
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(CONFIG_JSON['username'])
        logging.info('login: Username entered')
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(CONFIG_JSON['password'])
    logging.info('login: Password entered')
    time.sleep(1)

    sign_in_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    sign_in_button.click()
    logging.info('login: "Sign in" button found and click')
    time.sleep(3)

    # не всегда просит капчу, не просит видимо тогда, когда с данного устройства (ВДС) и с данного IP уже заходили в данную учетку
    # TODO здесь добавить решение гугл-капчи
    logging.info('login: Google reCaptcha solved')

    while True:
        try:
            wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
            break
        except TimeoutException:
            pass

    logging.info('login: stop')


def close_bk_message(webdriver_mar):
    logging.info('close_bk_message: start')
    wait_2 = WebDriverWait(webdriver_mar, 2)

    try:
        message_close_button = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, CLOSE_BK_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        logging.info('close_bk_message: No message from a bookmaker')  # сообщений/уведомлений от букера нет, закрывать окно не надо
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
        message_close_button = wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, CLOSE_PROMO_MESSAGE_BUTTON_CLASS)))
    except TimeoutException:
        logging.info('close_promo_message: No promo message from a bookmaker')  # сообщений/уведомлений от букера нет, закрывать окно не надо
        # TODO может ли быть два окна подряд? хз..хз...
        logging.info('close_promo_message: stop')
        return
    message_close_button.click()
    logging.info('close_promo_message: Close promo message button found and click')
    logging.info('close_promo_message: stop')


def search_event_by_teams(webdriver_mar, teams):
    logging.info('search_event_by_teams: start')
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        search_icon_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
        search_icon_button.click()
    except ElementClickInterceptedException as e:  # данное исключение бывает в том случае, если открыта и не решена гугл капча
        logging.info('search_event_by_teams: !!!GOOGLE CAPCHA!!! Search icon button found and not clickable')
        logging.info(str(e))
        logging.info('search_event_by_teams: stop')
        # time.sleep(7200)
        return
    logging.info('search_event_by_teams: Search icon button found and click')
    time.sleep(2.5)

    search_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(teams)
    logging.info('search_event_by_teams: Search field found and click, event_name enter')
    time.sleep(2.5)

    search_enter_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    logging.info('search_event_by_teams: Search enter button found and click')
    time.sleep(2.5)

    try:
        search_sport_tab_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException:
        logging.info('search_event_by_teams: Cannot click on the button (search_sport_tab_button) because no events were found')  # не найдено ни одного матча соответствующего поиску
        # TODO ну тут надо сделать уведомление, что ниче не найдено
        logging.info('search_event_by_teams: stop')
        return
    search_sport_tab_button.click()
    logging.info('search_event_by_teams: Search sports tab button found and click')
    time.sleep(1.5)

    logging.info('search_event_by_teams: stop')


def show_more_markets(webdriver_mar):
    logging.info('show_more_markets: start')
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    try:
        event_more_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, EVENT_MORE_BUTTON_CLASS)))
        event_more_button.click()
    except TimeoutException:
        logging.info('show_more_markets: Event more button not found')
        logging.info('show_more_markets: stop')
        #logging.info(e)  # штатная ситуация, наверное можно не писать об ошибке
        return
    logging.info('show_more_markets: Event more button found and click')
    time.sleep(1)

    all_markets_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, ALL_MARKETS_BUTTON_FPATH)))
    all_markets_button.click()
    logging.info('show_more_markets: Event all markets button found and click')
    time.sleep(1)
    logging.info('show_more_markets: stop')


def get_market_table_by_name(webdriver_mar, str):
    table_lst = []
    for table in webdriver_mar.find_elements_by_tag_name('div'):
        if table.get_attribute('class') == '':
            table_once = table.find_elements_by_class_name('market-table-name')
            if len(table_once) == 1:
                if table_once[0].text == str:
                    for table_once_tr in table.find_elements_by_tag_name('tr'):
                        for table_once_tr_td in table_once_tr.find_elements_by_tag_name('td'):
                            table_lst.append(table_once_tr_td)
                    return table_lst
                else:
                    continue

    logging.info('get_market_table_by_name: got table with coeff and markets')
    return


def sort_market_table_by_teamnumb(lst, team_num):
    new_lst = []
    if team_num == 1:
        for i in range(0, len(lst), 2):
            new_lst.append(lst[i])
    if team_num == 2:
        for i in range(1, len(lst), 2):
            new_lst.append(lst[i])
    logging.info('sort_market_table_by_teamnumb: create new list (teams/under/over)')
    return new_lst


def collect_handicap_str(str, handicap_value):
    if str == 'asia':
        if handicap_value < 0:
            str = f'({handicap_value + 0.25},{handicap_value - 0.25})'
            if handicap_value + 0.25 == 0:
                str = f'(0,{handicap_value - 0.25})'
            pass
        if handicap_value > 0:
            str = f'(+{handicap_value - 0.25},+{handicap_value + 0.25})'
            if handicap_value - 0.25 == 0:
                str = f'(0,+{handicap_value + 0.25})'
            pass
    elif str == 'simple':  # обычная фора
        if handicap_value == 0:
            str = '(0)'
        if handicap_value < 0:
            str = f'({handicap_value})'
        if handicap_value > 0:
            str = f'(+{handicap_value})'
        pass
    logging.info('collect_handicap_str: collect handicap string')
    return str


def collect_total_str(str, total_value):
    if str == 'asia':
        str = f'({total_value - 0.25},{total_value + 0.25})'
    elif str == 'simple':  # тотала 0 не бывает, минимум 0.5 и только положительный
        str = f'({total_value})'
    logging.info('collect_total_str: collect total string')
    return str


def change_language(webdriver_mar):
    wait_2 = WebDriverWait(webdriver_mar, 2)
    logging.info('change_language: start')

    close_bk_message(webdriver_mar)

    lang_settings_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]')))
    lang_settings_button.click()
    logging.info('change_language: found and click change language button')
    time.sleep(1)

    close_bk_message(webdriver_mar)

    languages_rus_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]/div[2]/div/div[2]/span[6]/span[2]')))
    languages_rus_button.click()
    logging.info('change_language: found and click change russian language button')
    time.sleep(1)

    logging.info('change_language: stop')


def start_marathon_bot(events_queue):
    webdriver_mar = get_driver('/GoogleChrome', CONFIG_JSON['username'])
    logging.info('Browser is open')

    wait_1 = WebDriverWait(webdriver_mar, 1)
    wait_3 = WebDriverWait(webdriver_mar, 3)
    wait_5 = WebDriverWait(webdriver_mar, 5)

    webdriver_mar.get(CONFIG_JSON['marathon_mirror'])
    logging.info("Marathon's page is open")

    log_in_marathonbet_account(webdriver_mar)  # вход в аккаунт

    close_bk_message(webdriver_mar)  # закрытие уведомления от букмекера
    close_promo_message(webdriver_mar)  # закрытие рекламного уведомления от букмекера

    change_language(webdriver_mar)  # сменить язык на русский

    close_bk_message(webdriver_mar)  # закрытие уведомления от букмекера
    close_promo_message(webdriver_mar)  # закрытие рекламного уведомления от букмекера

    N = 0
    datenow = None
    event = None
    events_dict = {}

    move_bets_history(events_dict)
    # events_dict = move_bets_history(events_dict)
    # TODO в очередь положить события, которые могут быть еще "сыграны"
    print(events_dict)

    while True:
        if event != None:
            if event['status'] == STATUS_BET_ACCEPTED:
                event['processing_time'] = convert_date_into_seconds(event['date_last_try']) - datenow
            teams = event['team1'] + ' - ' + event['team2']
            events_dict[teams + ' - ' + str(event['date_message_send'])] = event
            with open('bets.json', 'w', encoding=ENCODING) as f:
                json.dump(events_dict, f, indent=1, ensure_ascii=False)
            logging.info('bets.json updated')
            event = None
        logging.info('event is None')

        if events_queue.empty():
            # TODO добавить каждые 30 минут клики в "пустоту"
            logging.info('QUEUE is empty')
            time.sleep(2)
            continue
        else:
            event = events_queue.get()
            logging.info(f'Get event {event["date_added"]} from QUEUE')
            datenow = convert_date_into_seconds(datetime.now().strftime('%d-%m-%Y_%H-%M-%S'))
            diff_sec = datenow - convert_date_into_seconds(event['date_last_try'])
            if event['time_event_start'] != None:
                diff_sec2 = convert_start_time_match_into_seconds(event['time_event_start']) - datenow
            else:
                diff_sec2 = convert_start_time_match_into_seconds('23:59') - datenow
            if event['date_last_try'] != '00-00-0000_00-00-00':
                if (diff_sec < CONFIG_JSON["freq_update_sec"]) and (diff_sec2 > CONFIG_JSON['time_before_the_start']):    # if (diff_sec > FREQ_UPDATE_SEC) or (diff_sec2 < TIME_BEFORE_THE_START):
                                                                                            # событие будет возвращено в очередь,
                                                                                            # так как полчаса еще не прошло с момента последней попытки ИЛИ
                                                                                            # времени до начала события больше чем 15 минут
                    event['desc'] = 'insufficient time difference, pls wait'
                    events_queue.put_nowait(event)
                    logging.info(f'{diff_sec}<{CONFIG_JSON["freq_update_sec"]} and {diff_sec2}>{CONFIG_JSON["time_before_the_start"]} = TRUE. Event put back')
                    time.sleep(2)
                    continue
                if diff_sec > CONFIG_JSON["freq_update_sec"]:
                    event['desc'] = 'Event coeff will be updated'
                    logging.info('Event coeff will be updated')
                if diff_sec2 < CONFIG_JSON['time_before_the_start'] and N == 0:
                    N += 1
                    event['desc'] = 'Event soon started'
                    logging.info('Event soon started')
                # elif datenow > get_time_start(event['time_event_start']): # TODO delete это возможно не нужно, понаблюдать
                #     event['status'] = 'No bet'
                #     event['desc'] = 'Event has already begun'
                #     logging.info('No bet. Event has already begun')
                #     continue
            event['status'] = STATUS_IN_PROGRESS

        if event['sport'] == 'Теннис':  # найти собыйтие через поисковую строку, переключиться на вкладку "Спорт"  # TODO запихнуть это в if который ниже отвечает за поиск маркета
            search_event_by_teams(webdriver_mar, event['team1'])  # поиск события
        elif event['sport'] == 'Футбол' or event['sport'] == 'Хоккей':
            search_event_by_teams(webdriver_mar, event['team1'] + ' - ' + event['team2'])  # поиск события
        else:   # событие не надо обратно класть в очередь, оно уже было удалено из очереди,
                # надо просто изменить значение его полей и при заходе на новый цикл информация в файле bets будет обновлена
            logging.info('Event sport not defined')
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = STATUS_SPORT_NOT_DEFINED
            continue

        if event['id'] == None:
            try:  # найти айди события
                id = webdriver_mar.find_element_by_class_name(CATEGORY_CLASS).get_attribute('href')
            except NoSuchElementException as e:  # если событие не найдено через строку поиска, то перейти к следующему
                event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = STATUS_NO_SEARCH_RESULTS
                logging.info('Event not found on "Sport" TAB')
                logging.info(str(e))
                continue
            event['id'] = id[id.find('+-+') + 3:]

        if event['time_event_start'] == None:
            # try:  # найти время начала события
            event['time_event_start'] = webdriver_mar.find_element_by_class_name('date.date-short').text
            # except TimeoutException as e:  # если время начала события не нашлось, то установить "дефолтное" - 23:59  # TODO delete
            #     event['time_event_start'] = '23:59'
            #     event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            #     event['status'] = STATUS_NO_SEARCH_RESULTS
            #     events_queue.put_nowait(event)
            #     logging.info('Put event in QUEUE')
            #     logging.info('Event time start not found on "Sport" TAB')
            #     logging.info(str(e))
            #     continue

        event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
        time.sleep(1.5)
        choice_element = None
        try:  # если WHILE то continue, если if то pass
            if event['sport'] == 'Теннис':
                if event['type'][:2] == 'W1' or (event['type'][0] == '1' and len(event['type']) == 1):  # победа команды 1
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, TENNIS_WINNER1_BUTTON_FPATH)))
                    pass
                elif event['type'][:2] == 'W2' or (event['type'][0] == '2' and len(event['type']) == 1):  # победа команды 2
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, TENNIS_WINNER2_BUTTON_FPATH)))
                    pass
                else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                    logging.info('Event type not defined')
                    # TODO писать сообщение в конфу, что тип события не определен
                    event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = STATUS_TYPE_NOT_DEFINED
                    continue
            elif event['sport'] == 'Футбол':
                if event['type'][:2] == 'W1' or (event['type'][0] == '1' and len(event['type']) == 1):  # победа команды 1
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER1_BUTTON_FPATH)))
                    pass
                elif event['type'][:2] == '1X':  # 1X победа команды 1 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[6]')))
                    pass
                elif event['type'][:2] == 'W2' or (event['type'][0] == '2' and len(event['type']) == 1):  # победа команды 2
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER2_BUTTON_FPATH)))
                    pass
                elif event['type'][:2] == 'X2':  # X2 победа команды 2 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[8]')))
                    pass
                elif event['type'][0] == 'O' or event['type'][0] == 'U':  # тотал
                    show_more_markets(webdriver_mar)
                    total_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    total_asia = False
                    if total_value * 100 % 50 != 0:
                        total_asia = True
                    if total_asia:
                        total_str = collect_total_str('asia', total_value)
                        table_list = get_market_table_by_name(webdriver_mar, 'Азиатский тотал голов')
                    else:
                        total_str = collect_total_str('simple', total_value)
                        table_list = get_market_table_by_name(webdriver_mar, 'Тотал голов')
                    if event['type'][0] == 'U':  # тотал меньше
                        choice_list = sort_market_table_by_teamnumb(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(total_str) != -1:
                                break
                    elif event['type'][0] == 'O':  # тотал больше
                        choice_list = sort_market_table_by_teamnumb(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(total_str) != -1:
                                break
                elif event['type'][:2] == 'AH':  # азиатская фора или просто фора
                    show_more_markets(webdriver_mar)
                    handicap_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    handicap_asia = False
                    if handicap_value * 100 % 50 != 0:
                        handicap_asia = True
                    if handicap_asia:
                        handicap_str = collect_handicap_str('asia', handicap_value)
                        table_list = get_market_table_by_name(webdriver_mar, 'Победа с учетом азиатской форы')
                    else:
                        handicap_str = collect_handicap_str('simple', handicap_value)
                        table_list = get_market_table_by_name(webdriver_mar, 'Победа с учетом форы')
                    if event['type'][2] == '1':  # азиатская фора или просто фора на 1ю команду
                        choice_list = sort_market_table_by_teamnumb(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(handicap_str) != -1:
                                break
                    elif event['type'][2] == '2':  # азиатская фора или просто фора на 2ю команду
                        choice_list = sort_market_table_by_teamnumb(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(handicap_str) != -1:
                                break
                else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                    logging.info('Event type not defined')
                    # TODO писать сообщение в конфу, что тип события не определен
                    event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = STATUS_TYPE_NOT_DEFINED
                    continue
            elif event['sport'] == 'Хоккей':  # TODO бывает ли исход "победа или ничья"
                if event['type'][:2] == 'W1' or (event['type'][0] == '1' and len(event['type']) == 1):  # победа команды 1
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER1_BUTTON_FPATH)))
                    pass
                elif event['type'][:2] == '1X':  # 1X победа команды 1 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[6]')))
                    pass
                elif event['type'][:2] == 'W2' or (event['type'][0] == '2' and len(event['type']) == 1):  # победа команды 2
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER2_BUTTON_FPATH)))
                    pass
                elif event['type'][:2] == 'X2':  # X2 победа команды 2 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[8]')))
                    pass
                elif event['type'][0] == 'O' or event['type'][0] == 'U':  # тотал
                    show_more_markets(webdriver_mar)
                    total_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    total_str = collect_total_str('simple', total_value)
                    table_list = get_market_table_by_name(webdriver_mar, 'Тотал голов')
                    if event['type'][0] == 'U':  # тотал меньше
                        choice_list = sort_market_table_by_teamnumb(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(total_str) != -1:
                                break
                    elif event['type'][0] == 'O':  # тотал больше
                        choice_list = sort_market_table_by_teamnumb(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(total_str) != -1:
                                break
                elif event['type'][:2] == 'AH':  # азиатская фора или просто фора
                    show_more_markets(webdriver_mar)
                    handicap_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    handicap_str = collect_handicap_str('simple', handicap_value)
                    table_list = get_market_table_by_name(webdriver_mar, 'Победа с учетом форы')
                    if event['type'][2] == '1':  # азиатская фора или просто фора на 1ю команду
                        choice_list = sort_market_table_by_teamnumb(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(handicap_str) != -1:
                                break
                    elif event['type'][2] == '2':  # азиатская фора или просто фора на 2ю команду
                        choice_list = sort_market_table_by_teamnumb(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            if choice_element.text.find(handicap_str) != -1:
                                break
                else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                    logging.info('Event type not defined')
                    # TODO писать сообщение в конфу, что тип события не определен
                    event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = STATUS_TYPE_NOT_DEFINED
                    continue
        except StaleElementReferenceException as e:  # selenium.common.exceptions.StaleElementReferenceException: Message: stale element reference: element is not attached to the page document
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = STATUS_MARKET_NOT_FOUND
            events_queue.put_nowait(event)
            logging.info('Put event in QUEUE')
            logging.info('Market not found')
            logging.info(str(e))
            continue

        while True:  # сделал while, потому что хз как иначе сделать ожидание коэфициента, когда он не является кнопкой
            try:
                # TODO надо обновить страницу
                try:  # если в купоне есть событие(-ия), то купон будет очищен (теоретически в купоне не может быть больше чем 1 маркет)
                    coupon_delete_all = wait_1.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
                    coupon_delete_all.click()
                    time.sleep(1)
                    logging.info('Coupon cleared')
                except TimeoutException:
                    logging.info('Coupon is empty')
                    pass

                if choice_element != None:
                    # try:  # кликаем по найденному маркету
                    choice_element.click()
                    logging.info('Click on market')
                    time.sleep(1)
                    # except TimeoutException as e:  # TODO delete это можно удалить я думаю
                    #     event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    #     event['status'] = STATUS_MARKET_NOT_FOUND
                    #     events_queue.put_nowait(event)
                    #     logging.info('Put event in QUEUE')
                    #     logging.info('Market not found')
                    #     logging.info(str(e))
                    #     continue
                else:  # TODO а вот это нужно оставить
                    event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = STATUS_MARKET_NOT_FOUND
                    events_queue.put_nowait(event)
                    logging.info('Put event in QUEUE')
                    logging.info('Market not found')
                    break

                coeff_element = wait_1.until(ec.element_to_be_clickable((By.CLASS_NAME, 'choice-price')))  # ищем значение коэф-та в купоне TODO не работает с двумя и более выборами в одном купоне
                coupon_coeff = float(coeff_element.text[coeff_element.text.find(':') + 2:])
                event['coupon_coeff'] = coupon_coeff
                event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = 'Found coupon coeff'
                break
            except ValueError as e:  # TODO это исключение срабатывает в том случае, если коэффициент обновился уже будучи в купоне. НАДО: очистить купон, нажать на кэф снова.
                event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = 'Coupon coeff will be updated in coupon'
                coupon_delete_all = wait_1.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
                coupon_delete_all.click()
                time.sleep(1)
                events_queue.put_nowait(event)
                logging.info('Put event in QUEUE')
                logging.info('Coupon coeff will be updated in coupon')
                logging.info(str(e))
                webdriver_mar.refresh
                continue
            # except StaleElementReferenceException as e:  # TODO delete я хз, когда срабатывает это исключение... (предположение: срабаывает тогда, когда был клик на исход, но купон не успел отобразиться)
            #     event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            #     event['status'] = 'Cant found coupon coeff'
            #     time.sleep(1)
            #     events_queue.put_nowait(event)
            #     logging.info('Put event in QUEUE')
            #     logging.info('StaleElementReferenceException, i dont know what is it')
            #     logging.info(str(e))
            #     continue

        if event['status'] == STATUS_MARKET_NOT_FOUND:
            continue

        if (event['coeff'] - 0.2) > coupon_coeff:  # коэффициент в купоне не удовлетворяет условиям, событие будет отправлено в конец очереди
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = STATUS_NOT_TRY_COUPON_COEFF
            events_queue.put_nowait(event)
            logging.info("Not try coupon coeff")
            logging.info('Put event in QUEUE')
            continue
        # if (event['coeff'] * (100 - COEFF_DIFF_PERCENTAGE)/100) > coupon_coeff:  # запасной код на случай если понадобится сделать проценты
        #     logging.info(f"NOT TRY coeff: {coupon_coeff} event_coeff: {event['coeff']}")
        #     continue

        try:
            stake_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, STAKE_FIELD_CLASS)))  # в купоне вбиваем сумму ставки
            stake_field.clear()
            stake_field.send_keys(CONFIG_JSON['bet_mount_rub'])
            time.sleep(1)
            logging.info('Stake field found and bet amount entered')
        except Exception as e:  # вернул событие в очередь, может быть не надо?
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = 'Cant print bet mount in stake field'
            events_queue.put_nowait(event)
            logging.info('Cant print bet mount in stake field')
            logging.info('Put event in QUEUE')
            logging.info(str(e))
            continue

        try:
            stake_accept_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, STAKE_ACCEPT_BUTTON_XPATH)))  # "принять" ставку
            stake_accept_button.click()
            time.sleep(1)
            logging.info('Accept button found and click')
        except Exception as e:  # вернул событие в очередь, может быть не надо?
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = 'Cant click accept button'
            events_queue.put_nowait(event)
            logging.info('Cant click accept button')
            logging.info('Put event in QUEUE')
            logging.info(str(e))
            continue

        # TODO здесь должна быть проверка на то, что ставка принята

        try:  # TODO DELETE
            stake_OK_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="ok-button"]')))  # закрываем уведомление о том, что нехватка средств на счете
            stake_OK_button.click()
            logging.info('close message')
            time.sleep(2)
        except Exception as e:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
            event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = 'Cant click accept button'
            events_queue.put_nowait(event)
            logging.info('Cant click accept button')
            logging.info('Put event in QUEUE')
            logging.info(str(e))
            continue

        event['date_last_try'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
        event['status'] = STATUS_BET_ACCEPTED
        logging.info('Bet accepted')
        time.sleep(5) # TODO время ожидания после совершения ставки, сделать "рандомное" время на основе экспоненчиального закона


# def proc_start():
#     p_to_start = Process(target=start_marathon_bot, name='start_marathon_bot', args=(QUEUE, ))
#     p_to_start.start()
#     return p_to_start


# def proc_stop(p_to_stop):
#     p_to_stop.terminate()


def main():
    Process(target=start_marathon_bot, name='start_marathon_bot', args=(EVENTS_QUEUE,)).start()
    TELEGRAM_BOT.polling(none_stop=True, interval=0)


if __name__ == "__main__":  # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        logging.exception(str(e))
        a = str(input())  # TODO ставит бота на паузу, однако браузер закрывается
        raise e
