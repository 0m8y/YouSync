from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def accept_cookies(driver):
    if 'consent.youtube.com' in driver.current_url:
        try:
            accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Tout accepter')]")))
            accept_button.click()
        except Exception as e:
            print(f"Erreur lors de la tentative de clic sur le bouton 'Tout accepter': {e}")
    else:
        try:
            accept_button_xpath = '//button[@aria-label="Accepter l\'utilisation de cookies et d\'autres données aux fins décrites"]'
            accept_button = wait.until(EC.presence_of_element_located((By.XPATH, accept_button_xpath)))
            if accept_button:
                accept_button.click()
        except Exception as e:
            print(f"Erreur lors de la tentative de clic sur le bouton 'Tout accepter': {e}")

driver = webdriver.Chrome()

# Navigation vers YouTube
driver.get("https://www.youtube.com")
# Attente pour le chargement de la page et l'apparition du bouton de consentement
wait = WebDriverWait(driver, 10)
accept_cookies(driver)




# Ajoutez votre code de navigation ou d'interaction avec YouTube ici
time.sleep(30)
# N'oubliez pas de fermer le navigateur à la fin de vos opérations
driver.quit()
