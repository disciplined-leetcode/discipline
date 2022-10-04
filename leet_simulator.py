from dataclasses import dataclass

from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from selenium.webdriver.support.wait import WebDriverWait

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
# local is a dict with 3 keys: username, password, driver_path
from dotenv import load_dotenv

import os

DISCIPLINE_MODE = os.getenv('DISCIPLINE_MODE')

load_dotenv(f"{DISCIPLINE_MODE}.env")

class LeetCodeSimulator:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.login_status = False
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        if DISCIPLINE_MODE == 'dev':
            self.driver = webdriver.Chrome(os.getenv('DRIVER_PATH'), options=options)
        else:
            self.driver = webdriver.Chrome(Service(ChromeDriverManager().install()), options=options)

    def login(self):
        self.driver.get('https://leetcode.com/accounts/login/')

        while not self.driver.find_element(By.ID, 'id_login'):
            self.driver.implicitly_wait(1)

        self.driver.find_element(By.ID, 'id_login').send_keys(self.username)
        self.driver.find_element(By.ID, 'id_password').send_keys(self.password)
        self.driver.find_element(By.ID, 'id_password').send_keys(Keys.ENTER)

        self.login_status = True

    def get_submission_details(self, submission_id):
        if not self.login_status:
            self.login()

            # TODO: elegant way to wait for page to redirect
            # wait until url is leetcode.com
            while self.driver.current_url != 'https://leetcode.com/':
                self.driver.implicitly_wait(1)

        self.driver.get(f'https://leetcode.com/submissions/detail/{submission_id}/')

        # TODO: elegant way to wait code tag to load
        while not (codeblock := self.driver.find_element(By.TAG_NAME, 'code')):
            self.driver.implicitly_wait(1)

        lang = codeblock.get_attribute('class').removeprefix('language-')
        code = codeblock.text
        return f"```" + lang + '\n' + code + '\n' + "```"


# import asyncio

if __name__ == '__main__':
    leet = LeetCodeSimulator(os.getenv("LEETCODE_ACCOUNT_NAME"),
        os.getenv("LEETCODE_ACCOUNT_PASSWORD"))
    # leet should be stored to reuse the session
    code = leet.get_submission_details(811812564)
    print(code)
