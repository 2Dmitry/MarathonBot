import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from src.page_elements import *
from src.utils import logger_info_wrapper


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