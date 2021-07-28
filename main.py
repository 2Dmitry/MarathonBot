import time
import json
import os
import shutil
import multiprocessing
from datetime import datetime
from selenium.common.exceptions import TimeoutException, InvalidArgumentException
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
SIGN_IN_BUTTON_CLASS = 'form__element.auth-form__submit.auth-form__enter.green'
USERNAME_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__input'
PASSWORD_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__password'
MESSAGE_CLOSE_BUTTON_CLASS = 'button.btn-cancel.no.simplemodal-close'
SEARCH_ICON_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/button'
SEARCH_FIELD_CLASS = 'search-widget_input'
SEARCH_ENTER_BUTTON_XPATH = '//*[@id="header_container"]/div/div/div[1]/div[2]/div[2]/div/div[2]/div/div/div[1]/div/button[1]'
SEARCH_SPORTS_TAB_BUTTON_XPATH = '//*[@id="search-result-container"]/div[1]/div/button[3]/span'

# кнопки, которые есть в бк bet365
LOGIN_CONFIRM_BUTTON_CLASS = 'lms-StandardLogin_LoginButtonText'
OPTIONAL_ACCEPT_CLASS = 'accept-button'
ERROR_EVENT_CHECK_CLASS = 'panel-heading'
BALANCE_CLASS = "hm-MainHeaderMembersWide_Balance.hm-Balance"
ADDITIONAL_MESSAGES_FRAME_CLASS = 'lp-UserNotificationsPopup_Frame'
BET_LOGO_CLASS = 'hm-MainHeaderLogoWide_Bet365LogoImage'
BET_VALUE_FIELD_1_CLASS = 'bss-StakeBox_PermCount'
BET_VALUE_FIELD_2_CLASS = 'bss-StakeBox_StakeValueInput'
PLACE_BET_BUTTON_CLASS = 'bss-PlaceBetButton'
COEFF_VALUE_CLASS = 'bss-NormalBetItem_OddsContainer'
CLOSE_BET_BUTTON_CLASS = 'bss-DefaultContent_Close'
CONFIRM_DONE_BET_CLASS = 'bs-ReceiptContent_Done'
FAILED_BET_CLASS = 'bss-DefaultContent_Close'
ACCEPT_COEFF_CHANGE_CLASS = 'bs-AcceptButton'
BET_MENU_ICON = 'hm-MainHeaderMembersWide_MembersMenuIcon'
BET_REFRESH_BALANCE = 'um-BalanceRefreshButton_Icon'

# создаем необходимые папки
# os.makedirs('workdir', exist_ok=True)
os.makedirs('workdir/browser_profiles', exist_ok=True)
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
    wait_2 = WebDriverWait(driver_mar, 2)
    wait_3 = WebDriverWait(driver_mar, 3)
    wait_5 = WebDriverWait(driver_mar, 5)

    driver_mar.get(MARATHON_MIRROR)

    try:
        wait_2.until(ec.element_to_be_clickable((By.CLASS_NAME, 'marathon_icons-exit_icon')))
        return
    except TimeoutException:
        username_field = wait_3.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
        username_field.clear()
        username_field.send_keys(username)
        time.sleep(2)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(password)
    time.sleep(1)

    sign_in_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    sign_in_button.click()
    time.sleep(3)

    # не всегда просит капчу, не просит видимо тогда, когда с данного устройства (ВДС) и с данного IP уже заходили в данную учетку
    # TODO здесь добавить решение гугл-капчи


def close_message(driver_mar):
    wait_1 = WebDriverWait(driver_mar, 1)

    try:
        message_close_button = wait_1.until(ec.element_to_be_clickable((By.CLASS_NAME, MESSAGE_CLOSE_BUTTON_CLASS)))
    except TimeoutException:
        # сообщений никаких нет, закрывать окна не надо
        return
    message_close_button.click()
    time.sleep(1)


def search_event(driver_mar, event_name):
    wait_5 = WebDriverWait(driver_mar, 5)

    search_icon_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ICON_BUTTON_XPATH)))
    search_icon_button.click()
    time.sleep(1)

    search_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SEARCH_FIELD_CLASS)))
    search_field.clear()
    search_field.send_keys(event_name)
    time.sleep(1)

    search_enter_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_ENTER_BUTTON_XPATH)))
    search_enter_button.click()
    time.sleep(3)

    search_sport_tab_button = wait_5.until(ec.element_to_be_clickable((By.XPATH, SEARCH_SPORTS_TAB_BUTTON_XPATH)))
    search_sport_tab_button.click()
    time.sleep(1)

    event_more_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, 'event-more-view')))
    event_more_button.click()
    time.sleep(1)

def start_worker_mar(config, path, username, password):
    # спизжено с тырнета
    fileh = logging.FileHandler('workdir/logs/{}-{}.txt'.format(username, datetime.now().strftime('%d-%m-%Y_%H-%M-%S')), 'a', encoding='utf-8')
    logger = logging.getLogger(__name__)  # root logger
    formatter = logging.Formatter('%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
    fileh.setFormatter(formatter)
    for hdlr in logger.handlers[:]:  # remove all old handlers
        logger.removeHandler(hdlr)
    logger.addHandler(fileh)  # set the new handler
    logger.debug("thread module name {} start".format(__name__))
    # спизжено с тырнета </end>

    try:
        # if not os.path.isfile('{}/{}'.format(path, username)): # TODO что делают эти строки?
        #     shutil.rmtree('{}'.format(path))

        driver_mar = get_driver(path, username)
        time.sleep(3)

        wait_05 = WebDriverWait(driver_mar, 0.5)
        wait_1 = WebDriverWait(driver_mar, 1)
        wait_3 = WebDriverWait(driver_mar, 3)
        wait_5 = WebDriverWait(driver_mar, 5)

        login(driver_mar, username, password)
        close_message(driver_mar)
        event_name = 'Омония Никосия - Динамо Загреб'
        search_event(driver_mar, event_name)

        while True:
            # TODO шаги для совершения ставки здесь
            print('все готово')
            time.sleep(1)

        driver_bet365.close()
        quit()
    except Exception as e:
        logger.critical(e)
        raise e


def main():
    # TODO здесь сделать чтение конфиг-файла с настройками
    try:
        with open('config.json') as f:
            config_dict = json.load(f)
    except FileNotFoundError as e:
        # TODO следующие строчки кода не работают
        # ctypes.windll.user32.MessageBoxW(0,
        #                                  'Файл config.json не найден. Положите файл туда куда надо и перезапустите бота',
        #                                  "Warning", 1)
        raise e

    time.sleep(1)

    for acc in config_dict['accounts']:
        os.makedirs(acc['path'], exist_ok=True)
        Process(target=start_worker_mar, args=(config_dict, acc['path'], acc['username'], acc['password'])).start()




if __name__ == "__main__": # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        logging.critical(e)
        a = str(input()) # TODO что делает эта строчка?
        raise e