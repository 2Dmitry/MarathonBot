import logging

from selenium import webdriver
import re
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException


def logger_info_wrapper(func):
    def func_wrapper(*args):  # def func_wrapper(*args, **kwargs):
        logging.info(f'enter to function {func.__name__}')
        z = func(*args)
        logging.info(f'out from function {func.__name__}')
        return z
    return func_wrapper


class WaitForTextMatch(object):
    def __init__(self, locator, pattern):
        self.locator = locator
        self.pattern = re.compile(pattern)

    def __call__(self, driver):
        try:
            element_text = EC._find_element(driver, self.locator).text
            return self.pattern.search(element_text)
        except StaleElementReferenceException:
            return False


def get_driver(path_browser_profile, username):
    options = webdriver.ChromeOptions()
    options.add_argument("user-data-dir={}".format(path_browser_profile))
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["--enable-automation", "ignore-certificate-errors",
                                                        "safebrowsing-disable-download-protection",
                                                        "safebrowsing-disable-auto-update",
                                                        "disable-client-side-phishing-detection", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    # options.headless = True
    driver = webdriver.Chrome(options=options)
    open("{}/{}".format(path_browser_profile, username), "w").close()
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
      """
    })
    return driver
