import time
import json
import os
import shutil
import multiprocessing
from datetime import datetime
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, InvalidArgumentException
# from win32ctypes.core import ctypes
from src.utils import get_driver, WaitForTextMatch
from multiprocessing import Process, Queue
import pickle
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import logging
from src import *

# TODO  зеркало марафона меняется со временем, надо сделать обновление зеркала,
#       актуальаня инфа есть в Телеграме в бот-канале  "Зеркала букмекеров BK-INFO"
MARATHON_MIRROR = 'http://zerkalo.z0nd.xyz/?type=telegram_bot&bk=1'

# кнопки, которые есть в бк MarathonBet
EXIT_BUTTON_CLASS = 'marathon_icons-exit_icon'
USERNAME_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__input'
PASSWORD_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__password'
SIGN_IN_BUTTON_CLASS = 'form__element.auth-form__submit.auth-form__enter.green'
MESSAGE_CLOSE_BUTTON_CLASS = 'button.btn-cancel.no.simplemodal-close'
SEARCH_ICON_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/button'
SEARCH_FIELD_CLASS = 'search-widget_input'
SEARCH_ENTER_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/div/div[1]/div/button[1]'
SEARCH_SPORTS_TAB_BUTTON_XPATH = '//*[@id="search-result-container"]/div[1]/div/button[3]/span'
EVENT_MORE_BUTTON_CLASS = 'event-more-view'
STAKE_FIELD_CLASS = 'stake.stake-input.js-focusable'
STAKE_ACCEPT_BUTTON_XPATH = '//*[@id="betslip_placebet_btn_id"]'

# создаем необходимые папки
os.makedirs('workdir/logs', exist_ok=True)
os.makedirs('workdir/bets', exist_ok=True)
os.makedirs('workdir/history', exist_ok=True)

logging.basicConfig(filename="workdir/logs/{}.log".format(datetime.now().strftime('%d-%m-%Y_%H-%M-%S')),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)

# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.debug("Start")

# перемещаем историю сделанных ставок из корня проекта в соответсвующую папку
try:
    shutil.move('bets.json', 'workdir/bets/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
except FileNotFoundError:
    pass


def login(driver_mar, username, password):
    logging.debug('___login function start___')

    wait_2 = WebDriverWait(driver_mar, 2)
    wait_3 = WebDriverWait(driver_mar, 3)
    wait_5 = WebDriverWait(driver_mar, 5)

    driver_mar.get(MARATHON_MIRROR)
    logging.info('Opened the site page')  # открыл сраницу сайта

    try:
        wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, EXIT_BUTTON_CLASS)))
        logging.info('Exit button found: no need to login')
        logging.debug('___login function end___')
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(username)
        logging.exception('Username entered')
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(password)
    logging.info('Password entered')
    time.sleep(1)

    sign_in_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    sign_in_button.click()
    logging.info('"Sign in" button found and click')
    time.sleep(3)

    # не всегда просит капчу, не просит видимо тогда, когда с данного устройства (ВДС) и с данного IP уже заходили в данную учетку
    # TODO здесь добавить решение гугл-капчи
    logging.info('Google captcha solved')

    logging.debug('___login function end___')


def close_message(driver_mar):
    logging.debug('___close_message function start___')

    wait_1 = WebDriverWait(driver_mar, 1)

    try:
        message_close_button = wait_1.until(ec.element_to_be_clickable((By.CLASS_NAME, MESSAGE_CLOSE_BUTTON_CLASS)))
    except TimeoutException:
        logging.exception('No messages from a bookmaker') # сообщений/уведомлений от букера нет, закрывать окно не надо
        # TODO может ли быть два окна подряд? хз..хз...
        logging.debug('___close_message function end___')
        return
    message_close_button.click()
    logging.info('Close message button found and click')
    time.sleep(1)

    logging.debug('___close_message function end___')


def search_event(driver_mar, event_name):
    logging.debug('___search_event function start___')

    wait_5 = WebDriverWait(driver_mar, 5)

    search_icon_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
    try:
        search_icon_button.click()
    except ElementClickInterceptedException as e: # данное исключение бывает в том случае, если открыта и не решена гугл капча
        logging.exception('Search icon button not clickable')
        logging.critical(e)
        logging.debug('___search_event function end___')
        raise e
    logging.info('Search icon button found and click')
    time.sleep(1)

    search_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(event_name)
    logging.info('Search field found and click, event_name enter')
    time.sleep(1)

    search_enter_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    logging.info('Search enter button found and click')
    time.sleep(3)

    try:
        search_sport_tab_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    except TimeoutException as e:
        logging.debug('Cannot click on the button (search_sport_tab_button) because no events were found')
        # не найдено ни одного матча соответствующего поиску
        logging.exception(e)
        time.sleep(30)
        logging.debug('___search_event function end___')
        return
    search_sport_tab_button.click()
    logging.info('Search sports tab button found and click')
    time.sleep(1)

    event_more_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, EVENT_MORE_BUTTON_CLASS)))
    event_more_button.click()
    logging.info('Event more button found and click')
    time.sleep(1)

    logging.debug('___search_event function end___')


def start_worker_mar(config, path, username, password):
    # спизжено с тырнета
    fileh = logging.FileHandler('workdir/logs/{}-{}.txt'.format(username, datetime.now().strftime('%d-%m-%Y_%H-%M-%S')), 'a', encoding='utf-8')
    logger = logging.getLogger(__name__)  # root logger
    formatter = logging.Formatter('%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
    fileh.setFormatter(formatter)
    for hdlr in logger.handlers[:]:  # remove all old handlers
        logger.removeHandler(hdlr)
    logger.addHandler(fileh)  # set the new handler
    logger.debug("THREAD module name {} START".format(__name__))
    # спизжено с тырнета </end>

    try:
        # if not os.path.isfile('{}/{}'.format(path, username)): # TODO что делают эти строки?
        #     shutil.rmtree('{}'.format(path))

        driver_mar = get_driver(path, username)
        logger.info('Browser open')
        time.sleep(3)

        wait_05 = WebDriverWait(driver_mar, 0.5)
        wait_1 = WebDriverWait(driver_mar, 1)
        wait_3 = WebDriverWait(driver_mar, 3)
        wait_5 = WebDriverWait(driver_mar, 5)

        login(driver_mar, username, password) # вход в аккаунт

        close_message(driver_mar) # закрытие уведомления от букмекера

        search_event(driver_mar, 'Хонка - Домжале') # поиск события # TODO перенести это в цикл while-true

        # -----------TODO шаги для совершения ставки здесь это надо в цикл-----------
        # TODO выбрать исход и кликнуть по нему

        bet_mount = '200'  # TODO брать инфу из конфиг файла
        stake_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, STAKE_FIELD_CLASS))) # в купоне вбиваем сумму ставки
        stake_field.clear()
        stake_field.send_keys(bet_mount)
        logging.info('Field found and bet amount entered')
        time.sleep(1)

        # TODO проверка того, что кэф не изменился

        stake_accept_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, STAKE_ACCEPT_BUTTON_XPATH))) # "принять" ставку
        stake_accept_button.click()
        logging.info('Accept button found and click')
        time.sleep(1)
        # -----------TODO шаги для совершения ставки здесь это надо в цикл-----------

        logger.debug('FINISH') # TODO удалить строку

        while True:
            logger.debug('start of cycle')  # TODO удалить строку
            time.sleep(3)
            logger.debug('end of cycle')  # TODO удалить строку

        driver_bet365.close()
        quit()
    except Exception as e:
        logger.critical('-----НЕОБРАБАТЫВАЕМАЯ ОШИБКА-----')
        logger.critical(e)
        raise e


def main():
    try:
        with open('config.json') as f:
            config_dict = json.load(f)
            logging.info('Config file open')
    except FileNotFoundError as e:
        # TODO следующие 3 строчки кода не работают
        # ctypes.windll.user32.MessageBoxW(0,
        #                                  'Файл config.json не найден. Положите файл туда куда надо и перезапустите бота',
        #                                  "Warning", 1)
        logging.critical('CONFIG FILE NOT FOUND')
        logging.critical(e)
        raise e

    time.sleep(1)

    for acc in config_dict['account']:
        os.makedirs(acc['path'], exist_ok=True)
        Process(target=start_worker_mar, args=(config_dict, acc['path'], acc['username'], acc['password'])).start()


if __name__ == "__main__": # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()

    try:
        main()
    except Exception as e:
        logging.critical(e)
        a = str(input()) # TODO что делает эта строчка? херня какая-то
        raise e




    # П1:               <ссылка>
    # П2:               <ссылка>
    # Азиатские форы:   <ссылка>
    #                           АН1 от (-4.5 -5.0) до (+4.5 5.0)   <ссылки>
    #                           АН1 от(-4.5 - 5.0) до(+4.5 5.0)    <ссылки>
    # Тоталы        :   <ссылка>
    #                               ТМ от 0.5 до 10     <ссылки>
    #                               ТБ от 0 до 10       <ссылки>