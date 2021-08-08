import time
import json
import os
import shutil
import multiprocessing
from datetime import datetime
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, \
    StaleElementReferenceException
from src.utils import get_driver
from multiprocessing import Process, Queue
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import logging
import telebot  # Подключаем Telegram API
from telebot import types  # Подключаем библиотеку для создания кнопок


# EVENT STATUS
EVENT_NEW_STATUS = 'new'
EVENT_IN_PROGRESS_STATUS = 'in progress'
EVENT_NOT_FOUND_STATUS = 'event not found'
EVENT_TYPE_NOT_DEF_STATUS = "event's type not defined"
EVENT_SPORT_NOT_DEF_STATUS = "event's sport not defined"
EVENT_WAIT_MARKET_NOT_FOUND_STATUS = 'wait: market not found'
EVENT_COUPONCOEFF_NOT_GOOD_STATUS = 'coupon coeff isnot good'
EVENT_BET_ACCEPTED_STATUS = 'bet accepted'


# кнопки и поля, которые есть в бк MarathonBet
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

os.makedirs('workdir/logs', exist_ok=True)  # создаем необходимые папки
os.makedirs('workdir/bets', exist_ok=True)  # создаем необходимые папки
os.makedirs('workdir/history', exist_ok=True)  # создаем необходимые папки
logging.basicConfig(filename="workdir/logs/{}.log".format(datetime.now().strftime('%d-%m-%Y_%H-%M-%S')),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)
# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.debug('Start')
try:  # перемещаем историю сделанных ставок из корня проекта в соответсвующую папку
    shutil.move('bets.json', 'workdir/bets/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
except FileNotFoundError:
    pass

try:  # читаем конфиг файл
    with open('config.json') as f:
        CONFIG_JSON = json.load(f)
        logging.info('Config file open')
except FileNotFoundError as e:
    logging.exception(f'CONFIG FILE NOT FOUND \n{e}')
    raise e


# TODO зеркало марафона меняется со временем, надо сделать обновление зеркала,
#       актуальаня инфа есть в Телеграме в бот-канале  "Зеркала букмекеров BK-INFO"
# TODO сделать обновление конфиг файла из телеграм канала
MARATHON_MIRROR = CONFIG_JSON['marathon_mirror']
TELEGRAM_BOT = telebot.TeleBot(CONFIG_JSON['token'])
BOT_ID = CONFIG_JSON['bot_id']
PATH = CONFIG_JSON['path']
USERNAME = CONFIG_JSON['username']
PASSWORD = CONFIG_JSON['password']
BET_MOUNT_RUB = CONFIG_JSON['bet_mount_rub']
COEFF_DIFF_PERCENTAGE = CONFIG_JSON['coeff_diff_percentage']

QUEUE = Queue()
EVENTS = {}


def put_in_queue(text):
    event = {}                                                          # 0123456789@0123456789@0123456789@0123456789@0123456789@0123456789@012
    event['id'] = None
    event['date'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
    event['status'] = EVENT_NEW_STATUS
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
    event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
    # print(f'Событие которое получил бот: \n{event}\n')  # TODO DELETE
    logging.info(f'Событие которое получил бот: \n{event}\n')
    QUEUE.put_nowait(event)
    logging.info('Put event in QUEUE')


def update_config_file():
    with open('config.json', 'w') as f:
        json.dump(CONFIG_JSON, f, indent=1)
        logging.info('Config file saved')


@TELEGRAM_BOT.message_handler(content_types=['text'])
def get_text_messages(message):
    if message.text == 'bot id':
        TELEGRAM_BOT.send_message(message.from_user.id, BOT_ID)
    elif message.text == ('bot' + BOT_ID + ' привет'):
        TELEGRAM_BOT.send_message(message.from_user.id, 'bot' + BOT_ID + ' говорит: "Привет <3"')
    elif 0 < message.text.find(';'):
        put_in_queue(message.text)
        TELEGRAM_BOT.send_message(message.from_user.id, 'bot' + BOT_ID + ' получил событие')
    else:
        TELEGRAM_BOT.send_message(message.from_user.id, 'bot' + BOT_ID + ' вас не понимает')


def login(driver_mar):
    logging.info('login: start')

    wait_2 = WebDriverWait(driver_mar, 2)
    wait_3 = WebDriverWait(driver_mar, 3)
    wait_5 = WebDriverWait(driver_mar, 5)

    try:
        wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        logging.info('login: Exit button found: no need to login')
        logging.info('login: stop')
        CONFIG_JSON['first_try'] = False
        update_config_file()
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(USERNAME)
        logging.info('login: Username entered')
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(PASSWORD)
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
            if CONFIG_JSON['first_try']:
                logging.info('login: first try')
                CONFIG_JSON['first_try'] = False
                update_config_file()
            break
        except TimeoutException:
            pass

    logging.info('login: stop')


def close_bk_message(driver_mar):
    logging.info('close_bk_message: start')
    wait_2 = WebDriverWait(driver_mar, 2)

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


def close_promo_message(driver_mar):
    logging.info('close_promo_message: start')
    wait_2 = WebDriverWait(driver_mar, 2)

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


def search_event(driver_mar, event_name):
    logging.info('search_event: start')
    wait_3 = WebDriverWait(driver_mar, 3)
    wait_5 = WebDriverWait(driver_mar, 5)

    try:
        search_icon_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
        search_icon_button.click()
    except ElementClickInterceptedException as e:  # данное исключение бывает в том случае, если открыта и не решена гугл капча
        logging.info('search_event: !!!GOOGLE CAPCHA!!! Search icon button found and not clickable')
        logging.info(e)
        logging.info('search_event: stop')
        # time.sleep(7200)
        return
    logging.info('search_event: Search icon button found and click')
    time.sleep(1)

    search_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(event_name)
    logging.info('search_event: Search field found and click, event_name enter')
    time.sleep(1)

    search_enter_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    logging.info('search_event: Search enter button found and click')
    time.sleep(1)

    try:
        search_sport_tab_button = wait_3.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException as e:
        logging.info('search_event: Cannot click on the button (search_sport_tab_button) because no events were found')  # не найдено ни одного матча соответствующего поиску
        # TODO ну тут надо сделать уведомление, что ниче не найдено
        logging.info('search_event: stop')
        return
    search_sport_tab_button.click()
    logging.info('search_event: Search sports tab button found and click')
    time.sleep(0.66)

    event_more_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, EVENT_MORE_BUTTON_CLASS)))
    event_more_button.click()
    logging.info('search_event: Event more button found and click')
    time.sleep(0.66)

    event_more_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, ALL_MARKETS_BUTTON_FPATH)))
    event_more_button.click()
    logging.info('search_event: Event all markets button found and click')
    time.sleep(1)

    logging.info('search_event: stop')


def get_table_list(driver_mar, str):
    table_lst = []
    for table in driver_mar.find_elements_by_tag_name('div'):
        if table.get_attribute('class') == '':
            table_once = table.find_elements_by_class_name('market-table-name')
            if len(table_once) == 1:
                if table_once[0].text == str:
                    # print(table_once[0].text)  # TODO DELETE
                    for table_once_tr in table.find_elements_by_tag_name('tr'):
                        for table_once_tr_td in table_once_tr.find_elements_by_tag_name('td'):
                            table_lst.append(table_once_tr_td)
                            # print(f'{table_once_tr_td.text};\n')  # TODO DELETE
                    break
    logging.info(f'get_table_list: получена необходимая таблица с кэфами и выборами')
    return table_lst


def sort_table_list(lst, team_num):
    new_lst = []
    if team_num == 1:
        for i in range(0, len(lst), 2):
            new_lst.append(lst[i])
    if team_num == 2:
        for i in range(1, len(lst), 2):
            new_lst.append(lst[i])
    logging.info(f'get_table_list: создан новый лист в зависимости от команды/ или от больше/меньше, номер: {team_num}')
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
    if str == 'simple':  # обычная фора
        if handicap_value == 0:
            str = '(0)'
        if handicap_value < 0:
            str = f'({handicap_value})'
        if handicap_value > 0:
            str = f'(+{handicap_value})'
        pass
    logging.info(f'collect_handicap_str: сгенерирована строка, соответствующая форе: {str}')
    return str


def collect_total_str(total_value):
    if total_value == 0:
        str = f'(0)'
    else:
        str = f'({total_value})'
    logging.info(f'collect_total_str: сгенерирована строка, соответствующая тоталу: {str}')
    return str


def change_language(driver_mar):
    wait_2 = WebDriverWait(driver_mar, 2)
    logging.info(f'change_language: start')

    lang_settings_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]')))
    lang_settings_button.click()
    logging.info(f'change_language: найдена и нажата кнопка, отвечаюащя за смену языка')
    time.sleep(1)

    languages_rus_button = wait_2.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="language_form"]/div[2]/div/div[2]/span[6]/span[2]')))
    languages_rus_button.click()
    logging.info(f'change_language: найдена и нажата кнопка, отвечаюащя за переключение на русский язык')
    time.sleep(1)

    logging.info(f'change_language: stop')


def start_marathon_bot(QUEUE):
    driver_mar = get_driver(PATH, USERNAME)
    logging.info('Browser is open')

    wait_1 = WebDriverWait(driver_mar, 1)
    wait_3 = WebDriverWait(driver_mar, 3)
    wait_5 = WebDriverWait(driver_mar, 5)

    driver_mar.get(MARATHON_MIRROR)
    logging.info("Marathon's page is open")

    login(driver_mar)  # вход в аккаунт

    change_language(driver_mar)  # сменить язык на русский

    close_bk_message(driver_mar)  # закрытие уведомления от букмекера
    close_promo_message(driver_mar)  # закрытие рекламного уведомления от букмекера

    event = None
    try:
        while True:
            try:
                if event != None:  # and event['id'] in BETS:
                    teams = event['team1'] + ' - ' + event['team2']
                    EVENTS[teams + ' - ' + event['date']] = event
                    with open('bets.json', 'w', encoding='utf-8') as f:
                        json.dump(EVENTS, f, indent=1, ensure_ascii=False)
                        logging.info('EVENTS saved')
                    event = None
                logging.info('event is None')
            except ValueError:
                logging.info('Event isnot in list, dont need save')
                pass
            # TODO реализовать обновление информации о событиях, на которые не было сразу проставлено в течение дня
            if QUEUE.empty():
                # TODO добавить каждые 30 минут клики в "пустоту"
                logging.info('QUEUE is empty')
                time.sleep(1)
                continue
            else:
                event = QUEUE.get()
                logging.info('Get event from QUEUE')
                logging.info(f'{event}')
                event['status'] = EVENT_IN_PROGRESS_STATUS

            search_event(driver_mar, event['team1'] + ' - ' + event['team2'])  # поиск события

            try:
                event['id'] = driver_mar.find_element_by_class_name(CATEGORY_CLASS).get_attribute('href')
            except NoSuchElementException:  # если событие не найдено через строку поиска, то перейти к следующему
                event['status'] = EVENT_NOT_FOUND_STATUS
                continue
            event['id'] = event['id'][event['id'].find('+-+') + 3:]

            try:  # если в купоне есть событие(-ия), то купон будет очищен
                coupon_delete_all = wait_1.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
                coupon_delete_all.click()
            except TimeoutException:
                pass

            event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            time.sleep(0.5)
            if event['sport'] == 'Футбол':  # TODO только ФУТБОЛ, добавить п1/п2 в теннисе
                if event['type'][:2] == 'W1':  # победа команды 1
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER1_BUTTON_FPATH)))
                    choice_element.click()
                    # print('победа команды 1')  # TODO DELETE
                elif event['type'][:2] == '1X' or event['type'][:2] == 'X1':  # 1X победа команды 1 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[6]')))
                    choice_element.click()
                    # print('победа команды 1 или ничья')  # TODO DELETE
                elif event['type'][:2] == 'W2':  # победа команды 2
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, SOCCER_WINNER2_BUTTON_FPATH)))
                    choice_element.click()
                    # print('победа команды 2')  # TODO DELETE
                elif event['type'][:2] == '2X' or event['type'][:2] == 'X2':  # X2 победа команды 2 или ничья
                    choice_element = wait_5.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div[3]/div[2]/div[2]/div/div/div/div[2]/div/div/div/div/div[2]/table/tbody/tr/td[8]')))
                    choice_element.click()
                    # print('победа команды 2 или ничья')  # TODO DELETE
                elif event['type'][0] == 'O' or event['type'][0] == 'U':  # тотал
                    table_list = get_table_list(driver_mar, 'Тотал голов')
                    total_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    total_str = collect_total_str(total_value)
                    if event['type'][0] == 'U':  # тотал меньше
                        choice_list = sort_table_list(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            # print(f'{choice_element.text};')  # TODO DELETE
                            if choice_element.text.find(total_str) != -1:
                                choice_element.click()
                        # print('тотал меньше')
                    elif event['type'][0] == 'O':  # тотал больше
                        choice_list = sort_table_list(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            # print(f'{choice_element.text};')  # TODO DELETE
                            if choice_element.text.find(total_str) != -1:
                                choice_element.click()
                        # print(f'тотал больше')  # TODO DELETE
                elif event['type'][:2] == 'AH':  # азиатская фора или просто фора
                    handicap_value = float(event['type'][event['type'].find('(') + 1:event['type'].find(')')])
                    handicap_asia = False
                    if handicap_value * 100 % 50 != 0:
                        handicap_asia = True
                    if handicap_asia:
                        handicap_str = collect_handicap_str('asia', handicap_value)
                        # print(f'handicap_str: {handicap_str}')  # TODO DELETE
                        table_list = get_table_list(driver_mar, 'Победа с учетом азиатской форы')
                    else:
                        handicap_str = collect_handicap_str('simple', handicap_value)
                        # print(f'handicap_str: {handicap_str}')  # TODO DELETE
                        table_list = get_table_list(driver_mar, 'Победа с учетом форы')
                    if event['type'][2] == '1':  # азиатская фора или просто фора на 1ю команду
                        choice_list = sort_table_list(table_list, 1)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            # print(f'{choice_element.text};')  # TODO DELETE
                            if choice_element.text.find(handicap_str) != -1:
                                choice_element.click()
                        # print('азиатская фора или просто фора команда 1')  # TODO DELETE
                    elif event['type'][2] == '2':  # азиатская фора или просто фора на 2ю команду
                        choice_list = sort_table_list(table_list, 2)
                        while len(choice_list) > 1:
                            choice_element = choice_list.pop()
                            # print(f'{choice_element.text};')  # TODO DELETE
                            if choice_element.text.find(handicap_str) != -1:
                                choice_element.click()
                        # print('азиатская фора или просто фора команда 2')  # TODO DELETE
                else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                    logging.info(f'EVENT TYPE IS NOT DEFINED \n{event}\n')
                    # TODO писать сообщение в конфу, что тип события не определен
                    event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = EVENT_TYPE_NOT_DEF_STATUS
                    continue
            else:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                logging.info(f'EVENT SPORT IS NOT DEFINED\n {event} \n')
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = EVENT_SPORT_NOT_DEF_STATUS
                continue

            try:
                coeff_element = wait_1.until(ec.element_to_be_clickable((By.CLASS_NAME, 'choice-price')))  # ищем значение коэф-та в купоне TODO не работает с двумя и более выборами в одном купоне
            except TimeoutException:  # нужный исход не найден и поэтому событие добавляется в конец очереди
                logging.info(f'Нужный исход не найден')
                logging.info('Put event in QUEUE')
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = EVENT_WAIT_MARKET_NOT_FOUND_STATUS
                QUEUE.put_nowait(event)
                continue
            time.sleep(1)

            while True:  # сделал while, потому что хз как иначе сделать ожидание коэфициента, когда он не является кнопкой
                try:
                    coupon_coeff = float(coeff_element.text[coeff_element.text.find(':') + 2:])
                    event['coupon_coeff'] = coupon_coeff
                    event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = 'find coupon coeff'
                    break
                except ValueError:  # TODO это исключение срабатывает в том случае, если коэффициент обновился уже будучи в купоне. НАДО: очистить купон, нажать на кэф снова.
                    logging.info(f'Коэффициент купона обновился, когда уже был добавлен в купон')
                    coupon_delete_all = wait_1.until(ec.element_to_be_clickable((By.XPATH, '/html/body/div[12]/div/div[3]/div/div/div[2]/div/div[1]/div/div[1]/div[7]/table/tbody/tr/td/div/table[2]/tbody/tr[1]/td[1]/span')))
                    coupon_delete_all.click()
                    time.sleep(0.5)
                    choice_element.click()
                    time.sleep(0.5)
                    continue
                except StaleElementReferenceException:  # TODO я хз, когда срабатывает это исключение... (предположение: срабаывает тогда, когда был клик на исход, но купон не успел отобразиться)
                    logging.info(f'StaleElementReferenceException, хз что это за исключение и когда срабатывает\n {event} \n')
                    event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                    event['status'] = 'cant find coupon coeff'
                    time.sleep(0.5)
                    continue

            if (event['coeff'] - 0.2) > coupon_coeff:  # коэффициент в купоне не удовлетворяет условиям, событие будет отправлено в конец очереди
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = EVENT_COUPONCOEFF_NOT_GOOD_STATUS
                QUEUE.put_nowait(event)
                logging.info(f"NOT TRY COEFF -> coupon_coeff: {coupon_coeff} VS event_coeff: {event['coeff']}")
                logging.info('Put event in QUEUE')
                continue
            # if (event['coeff'] * (100 - COEFF_DIFF_PERCENTAGE)/100) > coupon_coeff:  # запасной код на случай если понадобится сделать проценты
            #     logging.info(f"NOT TRY coeff: {coupon_coeff} event_coeff: {event['coeff']}")
            #     continue

            try:
                stake_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, STAKE_FIELD_CLASS)))  # в купоне вбиваем сумму ставки
                stake_field.clear()
                stake_field.send_keys(BET_MOUNT_RUB)
                logging.info('Stake field found and bet amount entered')
                time.sleep(0.5)
            except BaseException:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = 'CANT PRINT BET MOUNT IN STAKE FIELD'
                logging.info('CANT PRINT BET MOUNT IN STAKE FIELD')
                continue

            try:
                stake_accept_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, STAKE_ACCEPT_BUTTON_XPATH)))  # "принять" ставку
                stake_accept_button.click()
                logging.info('Accept button found and click')
            except BaseException:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = 'CANT CLICK ACCEPT BUTTON'
                logging.info('CANT CLICK ACCEPT BUTTON')
                continue

            # TODO здесь должна быть проверка на то, что ставка принята

            try:
                stake_OK_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, '//*[@id="ok-button"]')))  # закрываем уведомление о том, что нехватка средств на счете
                stake_OK_button.click()
                logging.info('close message')
                time.sleep(3)
            except BaseException:  # событие не надо обратно класть в очередь, оно было удалено из очереди, надо просто записать его в историю ставок
                event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                event['status'] = 'CANT CLICK ACCEPT BUTTON'
                logging.info('CANT CLICK ACCEPT BUTTON')
                continue

            event['last_try_time'] = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
            event['status'] = EVENT_BET_ACCEPTED_STATUS
            logging.info('Bet accepted')
            time.sleep(5) # TODO время ожидания после совершения ставки, сделать "рандомное" время на основе экспоненчиального закона
    except Exception as e:
        logging.exception(e)
        driver_mar.close()  # TODO че делает эта строка?
        quit()
        raise e


# def proc_start():
#     p_to_start = Process(target=start_marathon_bot, name='start_marathon_bot', args=(QUEUE, ))
#     p_to_start.start()
#     return p_to_start


# def proc_stop(p_to_stop):
#     p_to_stop.terminate()


def main():
    Process(target=start_marathon_bot, name='start_marathon_bot', args=(QUEUE, )).start()
    TELEGRAM_BOT.polling(none_stop=True, interval=0)


if __name__ == "__main__":  # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        logging.exception(e)
        a = str(input())  # TODO что делает эта строчка? печатает в терминал ошибку?
        raise e
