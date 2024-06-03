import os
import random
import time
from selenium import webdriver
import selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import unittest


class BaseTestWebApp:
    @classmethod
    def setUpClass(cls):
        cls.PASSWORD_1 = 'Aa1!aaaa'
        cls.PASSWORD_2 = 'Bb2!bbbb'
        cls.HOST = 'http://localhost:8000'

        cls.driver = cls.init_driver()
        cls.last_name = ''.join(random.choices('абвгдеёжзиклмнопрстуфхчцшщъыьэюя', k=10)).capitalize()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_01_register(self):
        driver = self.driver
        driver.get(f'{self.HOST}/registration')
        driver.find_element(By.ID, "fullName").send_keys(f"{self.last_name} Тест Тестович") 
        driver.find_element(By.ID, "email").send_keys("test@test.ru") 
        driver.find_element(By.ID, "parentEmail").send_keys("parent@test.ru") 
        driver.find_element(By.ID, "password").send_keys(self.PASSWORD_1) 
        driver.find_element(By.ID, "confirmPassword").send_keys(self.PASSWORD_1) 
        driver.find_element(By.ID, "school").send_keys("Школа №99") 
        driver.find_element(By.ID, "schoolClass").send_keys("8") 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.find_element(By.ID, "birthDate").click()
        time.sleep(0.5)
        driver.find_element(By.CLASS_NAME, "today").click()
        driver.find_element(By.ID, "captcha").send_keys("1234") 
        driver.find_element(By.CLASS_NAME, "btn-primary").click()
        time.sleep(2)
        alert = driver.switch_to.alert
        self.assertEqual(alert.text, "Регистрация прошла успешно!")
        alert.accept()

    def test_02_logout(self):
        driver = self.driver
        driver.get(f'{self.HOST}/dashboard')
        try:
            driver.find_element(By.ID, "logout").click()
        except selenium.common.exceptions.ElementNotInteractableException:
            driver.find_element(By.CLASS_NAME, "navbar-toggler").click()
            time.sleep(1)
            driver.find_element(By.ID, "logout").click()
        time.sleep(2)
        self.assertEqual("Школа::Кода", driver.title)

    def test_03_login(self):
        driver = self.driver
        driver.get(f'{self.HOST}/login')
        driver.find_element(By.ID, "fullName").send_keys(f"{self.last_name} Тест Тестович")
        driver.find_element(By.ID, "birthDate").click()
        time.sleep(0.5)
        driver.find_element(By.CLASS_NAME, "today").click()
        driver.find_element(By.ID, "password").send_keys(self.PASSWORD_1) 
        driver.find_element(By.CLASS_NAME, "btn-primary").click()
        time.sleep(2)
        self.assertIn("Личный кабинет ШК", driver.title)

    def test_04_change_password(self):
        driver = self.driver
        driver.get(f'{self.HOST}/dashboard')
        driver.find_element(By.ID, "changePassword").click()
        time.sleep(1)
        driver.find_element(By.NAME, "old_password").send_keys(self.PASSWORD_1)
        driver.find_element(By.NAME, "new_password").send_keys(self.PASSWORD_2)
        driver.find_element(By.NAME, "new_password_confirm").send_keys(self.PASSWORD_2)
        driver.find_element(By.CLASS_NAME, "btn-primary").click()
        time.sleep(1)
        alert = driver.switch_to.alert
        self.assertEqual(alert.text, "Пароль успешно изменен")
        alert.accept()

    def test_05_fill_info(self):
        driver = self.driver
        driver.get(f'{self.HOST}/application')
        driver.find_element(By.ID, "unity-2024-04-10-rel-2024-04-16").click()
        driver.find_element(By.ID, "parentFullName").send_keys(f"{self.last_name} Тест Родитель")
        driver.execute_script("window.scrollTo(0, 500)")
        time.sleep(0.5)
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
        time.sleep(2)
        self.assertEqual(driver.current_url, f"{self.HOST}/application/fill_docs")  

    def test_06_fill_data(self):
        driver = self.driver
        driver.get(f'{self.HOST}/application')
        for picker in ("applicationFiles", "consentFiles", "parentPassportFiles", "childPassportFiles", "parentSnilsFiles", "childSnilsFiles"):
            driver.find_element(By.ID, picker).send_keys(os.path.abspath("data/static/icons/cs.png"))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.find_element(By.ID, "captcha").send_keys("1234") 
        driver.find_element(By.CLASS_NAME, "btn-primary").click()
        time.sleep(3)
        self.assertEqual(driver.current_url, f"{self.HOST}/application/waiting_confirmation")  

    def test_07_cancel_application(self):
        driver = self.driver
        driver.get(f'{self.HOST}/application')
        driver.find_element(By.ID, "cancel_btn").click()
        time.sleep(0.5)
        alert = driver.switch_to.alert
        self.assertEqual(alert.text, "Вы уверены, что хотите отозвать заявку?")  
        alert.accept()
        time.sleep(2)
        self.assertEqual(driver.current_url, f"{self.HOST}/application/fill_info")  


class TestWebAppChromeDesktop(BaseTestWebApp, unittest.TestCase):
    @classmethod
    def init_driver(cls):
        driver = webdriver.Chrome()
        driver.set_window_size(1600, 900)
        return driver

class TestWebAppChromeMobile(BaseTestWebApp, unittest.TestCase):
    @classmethod
    def init_driver(cls):
        driver = webdriver.Chrome()
        driver.set_window_size(540, 960)
        return driver

class TestWebAppFirefoxDesktop(BaseTestWebApp, unittest.TestCase):
    @classmethod
    def init_driver(cls):
        driver = webdriver.Firefox()
        driver.set_window_size(1600, 900)
        return driver

class TestWebAppFirefoxMobile(BaseTestWebApp, unittest.TestCase):
    @classmethod
    def init_driver(cls):
        driver = webdriver.Firefox()
        driver.set_window_size(540, 960)
        return driver

if __name__ == "__main__":
    unittest.main()
