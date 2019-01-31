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

    def __init__(self, username, account_no):
        self.username = username
        self.account_no = account_no

    def setup_browser(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")

        self.br = webdriver.Chrome(chrome_options=chrome_options)
        self.timeout = 30 # Request timeout in secs.

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