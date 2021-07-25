import time
import json
import os
import shutil
import multiprocessing
from datetime import datetime
from selenium.common.exceptions import TimeoutException, InvalidArgumentException
from win32ctypes.core import ctypes
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

# кнопки, которые есть в MarathonBet
SIGN_IN_BUTTON_CLASS = 'form__element.auth-form__submit.auth-form__enter.green'
USERNAME_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__input'
PASSWORD_FIELD_CLASS = 'form__element.form__element--br.form__input.auth-form__password'

# кнопки, которые есть в bet365
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
os.makedirs('logs', exist_ok=True)
os.makedirs('bets', exist_ok=True)

logging.basicConfig(filename="logs/{}.log".format(datetime.now().strftime('%d-%m-%Y_%H-%M-%S')),
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG)

# suppress logging from imported libraries / подавить ведение журнала из импортированных библиотек
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

logging.debug("Start")

# перемещаем историю сделанных ставок из корня проекта в соответсвующую папку
try:
    shutil.move('bets.json', 'bets/bets_{}.json'.format(datetime.now().strftime('%d_%m_%Y_%H_%M_%S')))
except FileNotFoundError:
    pass


def login(driver_mar, username, password):
    driver_mar.get(MARATHON_MIRROR)
    time.sleep(3)
    wait_5 = WebDriverWait(driver_mar, 5)
    wait_10 = WebDriverWait(driver_mar, 10)

    try:
        username_field = wait_10.until(ec.element_to_be_clickable((By.CLASS_NAME, USERNAME_FIELD_CLASS)))
    except TimeoutException:
        # мы уже залогинены
        return
    username_field.clear()
    username_field.send_keys(username)

    password_field = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, PASSWORD_FIELD_CLASS)))
    password_field.clear()
    password_field.send_keys(password)

    login_button = wait_5.until(ec.element_to_be_clickable((By.CLASS_NAME, SIGN_IN_BUTTON_CLASS)))
    login_button.click()
    time.sleep(5)

    # TODO здесь добавить решение гугл-капчи


def start_worker_mar(profile_path_mar, username, password):
    fileh = logging.FileHandler('logs/{}-{}.txt'.format(username, datetime.now().strftime('%d-%m-%Y_%H-%M-%S')), 'a', encoding='utf-8')
    logger = logging.getLogger(__name__)  # root logger
    formatter = logging.Formatter('%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
    fileh.setFormatter(formatter)
    for hdlr in logger.handlers[:]:  # remove all old handlers
        logger.removeHandler(hdlr)
    logger.addHandler(fileh)  # set the new handler
    logger.debug("thread module name {} start".format(__name__))



def main():
    # TODO здесь сделать чтение конфиг-файла с настройками
    # try:
    #     with open('config.json') as f:
    #         cfg_dict = json.load(f)
    # except FileNotFoundError as e:
    #     ctypes.windll.user32.MessageBoxW(0,
    #                                      'Файл config.json не найден. Положите файл туда куда надо и перезапустите бота',
    #                                      "Warning", 1)
    #     raise e

    time.sleep(5)
    # for acc in cfg_dict['accounts']:
    #     os.makedirs(acc['path'], exist_ok=True)
    #     Process(target=start_worker_mar, args=(acc['path'],
    #                                               acc['login'],
    #                                               acc['password'])).start()

    history = []
    idx = 0
    os.makedirs("history", exist_ok=True)


if __name__ == "__main__": # хз зачем это, скопировал из прошлого проекта
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        logging.critical(e)
        a = str(input())
        raise e