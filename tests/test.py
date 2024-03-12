from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from utils import *

def expand_description():
    driver = get_selenium_driver("https://www.youtube.com/watch?v=_Td7JjCTfyc&list=PLsOoDQgfBdd0wOkApkqy5VutMnoK2RKeK&index=1")

    show_description = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//tp-yt-paper-button[@id='expand']")))
    show_description.click()

    return driver

driver = expand_description()

time.sleep(30)
# N'oubliez pas de fermer le navigateur à la fin de vos opérations
driver.quit()
