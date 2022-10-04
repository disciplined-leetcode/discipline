import os
import re

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

DISCIPLINE_MODE = os.getenv('DISCIPLINE_MODE', "dev")

load_dotenv(f"{DISCIPLINE_MODE}.env")

class LeetCodeSimulator:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.login_status = False
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        if DISCIPLINE_MODE == 'prod':
            self.driver = webdriver.Chrome(Service(ChromeDriverManager().install()), options=options)
        else:
            self.driver = webdriver.Chrome(os.getenv('DRIVER_PATH'), options=options)

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

        source_code = self.driver.page_source

        # use regex to find runtime percentage like in "Your runtime beats 100.00 % of python3 submissions."
        # use regex to find memory percentage like in "Your memory usage beats 100.00 % of python3 submissions."
        runtime_percentage = re.search(r'runtime beats\n              (\d+.\d+)', source_code).group(1)
        memory_percentage = re.search(r'memory usage beats\n              (\d+.\d+)', source_code).group(1)
        lang = self.driver.find_element(By.CLASS_NAME, 'legendLabel').text.removesuffix('3')
        code = self.driver.find_element(By.CLASS_NAME, 'ace_text-layer').text

        return {
            'runtime': runtime_percentage,
            'memory': memory_percentage,
            'lang': lang,
            'code': f"```" + lang + '\n' + code + '\n' + "```"
        }


if __name__ == '__main__':
    leet = LeetCodeSimulator(os.getenv("LEETCODE_ACCOUNT_NAME"),
                             os.getenv("LEETCODE_ACCOUNT_PASSWORD"))
    # leet should be stored to reuse the session
    print(leet.get_submission_details(811812564))
