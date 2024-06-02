import datetime
import os
import random
import time
from selenium import webdriver
from selenium.webdriver.common.by import By


driver = webdriver.Chrome()
driver.get("http://localhost:8000")
driver.find_element(By.CLASS_NAME, "btn-success").click()

last_name = ''.join(random.choices('абвгдеёжзиклмнопрстуфхчцшщъыьэюя', k=10)).capitalize()
PASSWORD_1 = 'Aa1!aaaa'
PASSWORD_2 = 'Bb2!bbbb'


def test_register(driver):
    driver.get('http://localhost:8000/registration')
    driver.find_element(By.ID, "fullName").send_keys(f"{last_name} Тест Тестович") 
    driver.find_element(By.ID, "email").send_keys("test@test.ru") 
    driver.find_element(By.ID, "parentEmail").send_keys("parent@test.ru") 
    driver.find_element(By.ID, "password").send_keys("Aa1!aaaa") 
    driver.find_element(By.ID, "confirmPassword").send_keys(PASSWORD_1) 
    driver.find_element(By.ID, "school").send_keys("Школа №99") 
    driver.find_element(By.ID, "schoolClass").send_keys("8") 
    driver.find_element(By.ID, "birthDate").click()
    time.sleep(0.5)
    driver.find_element(By.CLASS_NAME, "today").click()
    driver.find_element(By.ID, "captcha").send_keys("1234") 
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.find_element(By.CLASS_NAME, "btn-primary").click()
    time.sleep(2)
    alert = driver.switch_to.alert
    alert.accept()

def test_logout(driver):
    driver.get('http://localhost:8000/dashboard')
    driver.find_element(By.ID, "logout").click()

def test_login(driver):
    driver.get('http://localhost:8000/login')
    driver.find_element(By.ID, "fullName").send_keys(f"{last_name} Тест Тестович")
    driver.find_element(By.ID, "birthDate").click()
    time.sleep(0.5)
    driver.find_element(By.CLASS_NAME, "today").click()
    driver.find_element(By.ID, "password").send_keys(PASSWORD_1) 
    driver.find_element(By.CLASS_NAME, "btn-primary").click()
    time.sleep(2)

def test_change_password(driver):
    driver.get('http://localhost:8000/dashboard')
    driver.find_element(By.ID, "changePassword").click()
    time.sleep(1)
    driver.find_element(By.NAME, "old_password").send_keys(PASSWORD_1)
    driver.find_element(By.NAME, "new_password").send_keys(PASSWORD_2)
    driver.find_element(By.NAME, "new_password_confirm").send_keys(PASSWORD_2)
    driver.find_element(By.CLASS_NAME, "btn-primary").click()
    time.sleep(1)
    alert = driver.switch_to.alert
    alert.accept()
    

def test_fill_info(driver):
    driver.get('http://localhost:8000/application')
    driver.find_element(By.ID, "unity-2024-04-10-rel-2024-04-16").click()
    driver.find_element(By.ID, "parentFullName").send_keys(f"{last_name} Тест Родитель")
    driver.find_element(By.ID, "parentBirthDate").click()
    time.sleep(0.5)
    driver.find_element(By.CLASS_NAME, "today").click()
    driver.find_element(By.ID, "parentAddress").send_keys("г. Москва, ул. Ленина, д. 1")
    driver.find_element(By.ID, "birthPlace").send_keys("г. Москва")
    driver.find_element(By.ID, "phone").send_keys("+7988123456")
    driver.find_element(By.ID, "parentPhone").send_keys("+7988123456")
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    driver.find_element(By.ID, "hasLaptop").click()
    driver.find_element(By.CLASS_NAME, "btn-primary").click()


def test_fill_data(driver):
    driver.get('http://localhost:8000/application')
    for picker in ("applicationFiles", "consentFiles", "parentPassportFiles", "childPassportFiles", "parentSnilsFiles", "childSnilsFiles"):
        driver.find_element(By.ID, picker).send_keys(os.path.abspath("data/static/icons/cs.png"))

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)

    driver.find_element(By.ID, "captcha").send_keys("1234") 

    driver.find_element(By.CLASS_NAME, "btn-primary").click()
    time.sleep(3)


def test_cancel_application(driver):
    driver.get('http://localhost:8000/application')
    driver.find_element(By.ID, "cancel_btn").click()
    time.sleep(0.5)
    alert = driver.switch_to.alert
    alert.accept()
    

test_register(driver)
test_logout(driver)
test_login(driver)
test_change_password(driver)
test_fill_info(driver)
test_fill_data(driver)
test_cancel_application(driver)
test_logout(driver)
time.sleep(3)
