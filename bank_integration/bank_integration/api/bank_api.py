# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import frappe
import bank_integration
from frappe.utils.file_manager import save_file

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By


class BankAPI:
    def __init__(
        self,
        username=None,
        password=None,
        timeout=30,
        logged_in=0,
        doctype=None,
        docname=None,
        uid=None,
        resume=False,
        data=None,
    ):
        self.username = username
        self.password = password
        self.timeout = timeout
        self.logged_in = logged_in
        self.doctype = doctype
        self.docname = docname
        self.uid = uid or frappe.utils.random_string(7)
        self.cache_key = "bank_" + self.uid
        self.data = data

        if getattr(self, "init"):
            self.init()

        if resume:
            self.resume_session()
        else:
            self.login()

    def login(self):
        pass

    def logout(self):
        pass

    def setup_browser(self):
        self.br = webdriver.Chrome()

    def get_options(self):
        options = Options()
        options.add_argument("window-size=990,1200")
        if not frappe.conf.developer_mode:
            options.add_argument("--headless")

        return options

    def emit_js(self, js):
        js = "if (cur_frm && cur_frm._uid === '{0}') {{ {1} }}".format(self.uid, js)
        frappe.publish_realtime(
            "eval_js",
            js,
            user=frappe.session.user,
            doctype=self.doctype,
            docname=self.docname,
        )

    def show_msg(self, msg):
        self.emit_js("frappe.update_msgprint(`{0}`);".format(msg))

    def get_resume_info(self):
        return {
            "executor_url": self.br.command_executor._url,
            "session_id": self.br.session_id,
        }

    def resume_session(self):
        cached = frappe.cache().get_value(self.cache_key, user=frappe.session.user)
        if not cached:
            self.throw("Unable to find session info in cache")

        self.data = frappe._dict(cached["data"] or {})
        resume_info = frappe._dict(cached["resume_info"])

        self.br = webdriver.Remote(
            command_executor=resume_info.executor_url, options=self.get_options()
        )
        self.br.close()
        self.br.session_id = resume_info.session_id

    def wait_until(self, ec, timeout=None, throw=True):
        try:
            return WebDriverWait(self.br, timeout or self.timeout).until(ec)
        except TimeoutException:
            self.handle_exception(throw)

    def switch_to_frame(self, selector, selector_type="name"):
        self.br.switch_to.default_content()
        self.wait_until(
            EC.frame_to_be_available_and_switch_to_it(
                (getattr(By, selector_type.upper()), selector)
            )
        )

    def get_element(
        self, selector, selector_type="name", timeout=None, throw=True, now=False
    ):
        if not now:
            return self.wait_until(
                EC.visibility_of_element_located(
                    (getattr(By, selector_type.upper()), selector)
                ),
                timeout=timeout,
                throw=throw,
            )
        else:
            try:
                return self.br.find_element(
                    getattr(By, selector_type.upper()), selector
                )
            except NoSuchElementException:
                self.handle_exception(throw, selector)

    def handle_exception(self, throw, selector=None):
        if throw == "ignore":
            pass
        elif throw:
            if not selector:
                self.throw(
                    "Timed out waiting for element to be present", screenshot=True
                )
            else:
                self.throw("Element not found: " + selector)
        else:
            raise

    def throw(self, message, screenshot=False):
        js = "frappe.hide_msgprint();"
        if screenshot:
            save_file(
                "payment_error_{}.png".format(self.uid),
                self.br.get_screenshot_as_png(),
                self.doctype,
                self.docname,
                is_private=1,
            )

            frappe.db.commit()
            js += " if (cur_frm) cur_frm.reload_doc();"
            message += " (See attached screenshot)"

        self.emit_js(js)
        self.logout()
        frappe.throw(message)

    def save_for_later(self):
        frappe.cache().set_value(
            self.cache_key,
            {"resume_info": self.get_resume_info(), "data": self.data},
            user=frappe.session.user,
        )

        setattr(bank_integration, self.cache_key, self)

    def delete_cache(self):
        frappe.cache().delete_key(self.cache_key, user=frappe.session.user)

        if hasattr(bank_integration, self.cache_key):
            delattr(bank_integration, self.cache_key)


class AnyEC:
    """Use with WebDriverWait to combine expected_conditions
    in an OR.
    """

    def __init__(self, *args):
        self.ecs = args

    def __call__(self, driver):
        driver._found_element = None
        for fn in self.ecs:
            try:
                if fn(driver):
                    element = getattr(fn, "locator", None)
                    if element:
                        driver._found_element = element
                    elif "alert" in str(fn):
                        driver._found_element = "alert"
                    return True
            except:
                pass
