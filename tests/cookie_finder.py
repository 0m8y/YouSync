from selenium import webdriver
import time

def get_cookie_information():
    driver = webdriver.Chrome()
    driver.get("https://www.youtube.com")

    input("Après avoir accepté les conditions, appuyez sur Entrée dans ce terminal...")

    cookie = driver.get_cookie('CONSENT')

    print(cookie)

    driver.quit()

# Remplacez ceci par la valeur réelle de votre cookie
cookie = {
    'name': 'CONSENT', 
    'value': 'PENDING+117',
    'domain': '.youtube.com', 
    'expiry': 1738961135, 
    'path': '/'
    }
# Configurez votre driver Selenium (Chrome dans cet exemple)
driver = webdriver.Chrome()

# Ouvrez YouTube pour pouvoir définir des cookies
driver.get("https://www.youtube.com")

time.sleep(4)

# Ajoutez le cookie à votre session
driver.add_cookie(cookie)
print('cookie ajouté')

# Maintenant, lorsque vous naviguerez sur YouTube, le cookie sera inclus
driver.get("https://www.youtube.com")

time.sleep(20)

# Votre code ici...

driver.quit()