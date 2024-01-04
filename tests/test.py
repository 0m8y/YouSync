from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from pytube import YouTube

url = "https://www.youtube.com/watch?v=-iaSs5pt5mM&list=PLsOoDQgfBdd3rEtl2weVQ6XnQN421ODzq&index=10"

chrome_profile_path = r'C:\Users\msoub\AppData\Local\Google\Chrome\User Data'
chrome_options = Options()
# chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
# chrome_options.add_argument("--profile-directory=Default")

driver = webdriver.Chrome(options=chrome_options)

driver.get(url)

time.sleep(5)

WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Tout accepter')]")))
driver.find_element("xpath", "//span[contains(text(), 'Tout accepter')]").click()

# show_description = WebDriverWait(driver, 20).until(
#         EC.element_to_be_clickable((By.XPATH, "//tp-yt-paper-button[@id='expand']"))
#     )

# show_description.click()

time.sleep(20)

driver.quit()