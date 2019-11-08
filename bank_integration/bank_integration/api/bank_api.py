# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import frappe
from abc import ABCMeta, abstractmethod

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class BankAPI:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.timeout = 30 # Request timeout in secs.

    def get_options(self):
        options = Options()
        # Comment out for debugging
        options.add_argument("--headless")
        options.add_experimental_option('w3c', False)

        return options

    def setup_browser(self):
        self.br = webdriver.Chrome(options=self.get_options(), port=12345)

    def get_resume_info(self):
        return {
            'executor_url': self.br.command_executor._url,
            'session_id': self.br.session_id
        }

    def resume_session(self, executor_url, session_id):
        self.br = webdriver.Remote(command_executor=executor_url,
            options=self.get_options())
        self.br.close()
        self.br.session_id = session_id

    def throw(self, message, logout=False):
        frappe.emit_js("frappe.hide_msgprint();")
        if logout:
            self.logout()
        else:
            self.br.quit()
        frappe.throw(message)


class AnyEC:
    """ Use with WebDriverWait to combine expected_conditions
        in an OR.
    """
    def __init__(self, *args):
        self.ecs = args
    def __call__(self, driver):
        driver._found_element = None
        for fn in self.ecs:
            try:
                if fn(driver):
                    element = getattr(fn, 'locator', None)
                    if element:
                        driver._found_element = element
                    elif 'alert' in str(fn):
                        driver._found_element = 'alert'
                    return True
            except:
                pass