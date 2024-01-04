from audio_downloader import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time

def scroll_down_page(driver):
    last_height = driver.execute_script("return document.documentElement.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")

        time.sleep(1)

        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_video_urls_from_driver(driver):
    video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')

    video_urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]

    recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
    if recommended_videos_present:
        video_urls = video_urls[:-5]
    return video_urls

def get_all_video_links_from_playlist(url):
    chrome_profile_path = r'C:\Users\msoub\AppData\Local\Google\Chrome\User Data'
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)

    WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
    scroll_down_page(driver)

    video_urls = get_video_urls_from_driver(driver)

    driver.quit()

    print(str(len(video_urls)) + " videos trouvée")
    return video_urls

