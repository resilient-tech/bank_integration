# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import time
import tempfile
import os
import glob

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
        bulk_payments=None,
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
        self.bulk_payments = bulk_payments
        self.remove_payment = True
        if bulk_payments is None:
            self.is_bulk_payments = False
        else:
            self.is_bulk_payments = True

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
        from selenium.webdriver.remote.remote_connection import RemoteConnection

        if not isinstance(RemoteConnection._timeout, (int, float)):
            RemoteConnection.set_timeout(90)

        self.download_dir = tempfile.mkdtemp(prefix="bank_dl_")

        self.br = webdriver.Chrome(options=self.get_options())

        # Enable downloads for headless Chrome
        self.br.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": self.download_dir,
            },
        )

    def get_options(self):
        options = Options()
        options.add_argument("--window-size=990,1200")

        options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )

        if self.download_dir and os.path.isdir(self.download_dir):
            options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": self.download_dir,
                    "download.prompt_for_download": False,
                    "plugins.always_open_pdf_externally": True,
                },
            )

        if not frappe.conf.developer_mode:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")

        return options

    def show_msg(self, msg):
        frappe.publish_realtime(
            "bi_action",
            {"message": msg, "uid": self.uid, "action": "show_message"},
            user=frappe.session.user,
            doctype=self.doctype,
            docname=self.docname,
        )

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

        if "bulk_data" in cached:
            self.bulk_payments = cached["bulk_data"]
        if "is_bulk_payments" in cached:
            self.is_bulk_payments = cached["is_bulk_payments"]
        if "remove_payment" in cached:
            self.remove_payment = cached["remove_payment"]

        resume_info = frappe._dict(cached["resume_info"])

        self.download_dir = cached.get("download_dir") or ""

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
        if screenshot:
            save_file(
                "payment_error_{}.png".format(self.uid),
                self.br.get_screenshot_as_png(),
                self.doctype,
                self.docname,
                is_private=1,
            )

            frappe.db.commit()
            message += " (See attached screenshot)"

        frappe.publish_realtime(
            "bi_action",
            {"docname": self.docname, "uid": self.uid, "action": "reload_doc"},
            user=frappe.session.user,
            doctype=self.doctype,
            docname=self.docname,
        )
        self.logout()
        frappe.throw(message)

    def save_for_later(self):
        if not self.is_bulk_payments:
            frappe.cache().set_value(
                self.cache_key,
                {"resume_info": self.get_resume_info(),
                "data": self.data,
                "download_dir": getattr(self, "download_dir", None),
                },
                user=frappe.session.user,
            )
        else:
            frappe.cache().set_value(
                self.cache_key,
                {
                    "resume_info": self.get_resume_info(),
                    "data": self.data,
                    "bulk_data": self.bulk_payments,
                    "is_bulk_payments": self.is_bulk_payments,
                    "remove_payment":self.remove_payment,
                    "download_dir": getattr(self, "download_dir", None),
                },
                user=frappe.session.user,
            )
        setattr(bank_integration, self.cache_key, self)

    def delete_cache(self):
        frappe.cache().delete_key(self.cache_key, user=frappe.session.user)

        if hasattr(bank_integration, self.cache_key):
            delattr(bank_integration, self.cache_key)

    def wait_for_download(self, expected_filename=None, timeout=30):
        """Wait for a file to finish downloading in self.download_dir.
        Returns (filename, file_content_bytes) or (None, None) on timeout.
        Ignores Chrome's partial .crdownload files.
        """

        if not getattr(self, "download_dir", None) or not os.path.isdir(
            self.download_dir
        ):
            return None, None

        for _ in range(timeout * 2):
            files = glob.glob(os.path.join(self.download_dir, "*"))
            done = [f for f in files if not f.endswith(".crdownload")]
            if expected_filename:
                done = [f for f in done if os.path.basename(f) == expected_filename]
            if done:
                filepath = done[0]
                size1 = os.path.getsize(filepath)
                time.sleep(0.2)
                size2 = os.path.getsize(filepath)
                if size1 == size2 and size1 > 0:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    return os.path.basename(filepath), content
            time.sleep(0.5)
        return None, None

    def cleanup_download_dir(self, delete_dir=False):
        """Clear the contents of the temp download directory.
        If delete_dir is True, also remove the directory itself.
        """
        import os
        import shutil

        if hasattr(self, "download_dir") and self.download_dir:
            try:
                for entry in os.scandir(self.download_dir):
                    if entry.is_dir(follow_symlinks=False):
                        shutil.rmtree(entry.path)
                    else:
                        os.remove(entry.path)
                if delete_dir:
                    os.rmdir(self.download_dir)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "Failed to cleanup payment receipt download directory: {}".format(
                        self.download_dir
                    ),
                )


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
