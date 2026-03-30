# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import time

import frappe
import hashlib
from frappe.utils import getdate, today, add_months, add_days, flt
from frappe.utils.file_manager import save_file

from bank_integration.bank_integration.api.bank_api import BankAPI, AnyEC

# Selenium imports
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoAlertPresentException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys
from .decorators import set_correct_payment_data


class HDFCBankAPI(BankAPI):
    def init(self):
        self.bank_name = "HDFC Bank"

    def login(self):
        self.show_msg("Attempting login...")
        self.setup_browser()
        self.br.get("https://netbanking.hdfcbank.com/netbanking/")

        self.switch_to_frame("login_page")
        cust_id = self.get_element("fldLoginUserId")
        cust_id.send_keys(self.username, Keys.ENTER)

        self.br.switch_to.default_content()
        pass_input = self.get_element("password", "id", timeout=10, throw="ignore")
        if pass_input is None:
            self.throw(
                "Credentials are incorrect. Please verify the username & password in Bank Integration Settings."
            )
        pass_input.send_keys(self.password, Keys.ENTER)

        self.br.switch_to.default_content()
        self._handle_post_login_state()

    def _handle_post_login_state(self):
        """
        After password submission, HDFC can land on different screens:
          1. Invalid credentials error
          2. Password expired screen (fldOldPass)
          3. "Already logged in" dialog with a Proceed button (proceedBtn).
             This dialog can appear up to 2 times back-to-back.
          4. OTP screen (mfa-get-otp-btn)
          5. Security questions screen (fldAnswer)
          6. Angular dashboard (bb-retail-layout tag) — direct login success
        We loop up to 3 times so we can dismiss up to 2 proceed dialogs before
        reaching the final state.
        """

        for _ in range(3):
            self.wait_until(
                AnyEC(
                    EC.visibility_of_element_located(
                        (
                            By.XPATH,
                            "//td/span[text()[contains(.,'The Customer ID/IPIN (Password) is invalid.')]]",
                        )
                    ),
                    EC.visibility_of_element_located((By.ID, "proceedBtn")),
                    EC.visibility_of_element_located((By.ID, "mfa-get-otp-btn")),
                    EC.presence_of_element_located((By.TAG_NAME, "bb-retail-layout")),
                    EC.visibility_of_element_located((By.NAME, "fldOldPass")),
                    EC.visibility_of_element_located((By.NAME, "fldAnswer")),
                ),
                throw="ignore",
                timeout=10,
            )
            # NOTE: The 'fldOldPass' and 'fldAnswer' conditions are not hit in the
            # current HDFC UI. We still include them here so future maintainers know
            # there is existing logic to handle password-expiry and security-question
            # screens if the bank reintroduces them.
            found = self.br._found_element

            if not found:
                if self.get_element(
                    '//*[@id="bb-modal-dialog-header" and normalize-space(text())="Please reset your password!"]',
                    "xpath",
                    now=True,
                    throw="ignore",
                ):
                    self.throw(
                        "Please reset your password manually at the hdfc netbanking portal"
                    )
                if self.br.find_elements(By.ID, "mfa-get-otp-btn"):
                    self.process_otp()
                    return
                if self.br.find_elements(By.ID, "proceedBtn"):
                    self.br.find_element(By.ID, "proceedBtn").click()
                    continue
                self.handle_login_error()
                return

            last = found[-1]

            if "is invalid" in last:
                self.throw(
                    "The password you've set in Bank Integration Settings is incorrect."
                )

            elif last == "fldOldPass":
                self.throw(
                    "The password you've set has expired. "
                    "Please set a new password manually and update the same in Bank Integration Settings."
                )

            elif last == "proceedBtn":
                self.get_element("proceedBtn", "id", now=True).click()
                continue

            elif last == "fldAnswer":
                self.process_security_questions()
                return

            elif last == "mfa-get-otp-btn":
                self.process_otp()
                return

            elif last == "bb-retail-layout":
                if self.br.find_elements(By.ID, "mfa-get-otp-btn"):
                    self.process_otp()
                else:
                    self.login_success()
                return

            else:
                self.handle_login_error()
                return

        self.handle_login_error()

    def process_otp(self):

        try:
            self.wait_until(
                AnyEC(
                    EC.visibility_of_element_located(
                        (
                            By.XPATH,
                            '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]',
                        )
                    ),
                    EC.presence_of_element_located((By.ID, "mfa-get-otp-btn")),
                ),
                throw=False,
            )
        except Exception:
            self.throw(
                "Failed to find Get Otp Button. Payment is not successful.",
                screenshot=True,
            )

        if (
            '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]'
            == self.br._found_element[-1]
        ):
            try:
                email_mobile_otp_label = self.get_element(
                    '//label[@data-role="radio-group-option"][.//span[contains(text(),"SMS") and contains(text(),"email")]]',
                    "xpath",
                )
                self.br.execute_script("arguments[0].click();", email_mobile_otp_label)
            except Exception:
                pass
            get_otp_btn = self.get_element(
                '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]',
                "xpath",
                now=True,
            )
            get_otp_btn.click()
        elif "mfa-get-otp-btn" == self.br._found_element[-1]:
            try:
                email_mobile_otp_radio = self.get_element(
                    "channel-BOTH", "id", now=True
                )
                email_mobile_otp_radio.click()
            except Exception:
                pass
            otp_btn = self.get_element("mfa-get-otp-btn", "id", now=True)
            self.br.execute_script("arguments[0].click();", otp_btn)

        self.br.switch_to.default_content()
        input_msg = ""
        if (
            '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]'
            == self.br._found_element[-1]
        ):
            try:
                input_msg = self.get_element(
                    'label[for="otpValue"]', "css_selector"
                ).text
            except Exception:
                pass

        # here both listeners for list and form view and kept separate as they require
        # cur_list and cur_frm respectively
        bulk = ""
        if self.is_bulk_payments:
            bulk = "_bulk"

        frappe.publish_realtime(
            "get_bank_otp" + bulk,
            {
                "message": input_msg,
                "uid": self.uid,
                "bank_name": self.bank_name,
                "logged_in": self.logged_in,
            },
            user=frappe.session.user,
            doctype=self.doctype,
            docname=self.docname,
        )

        self.save_for_later()

    def process_security_questions(self):
        frappe.publish_realtime(
            "get_bank_answers",
            {
                "questions": self.get_question_map(),
                "uid": self.uid,
                "bank_name": self.bank_name,
                "logged_in": self.logged_in,
            },
            user=frappe.session.user,
            doctype=self.doctype,
            docname=self.docname,
        )

        self.save_for_later()

    def get_question_map(self, get_fields=False):
        question_elements = self.br.find_elements(By.NAME, "fldQuestionText")
        answer_elements = self.br.find_elements(By.NAME, "fldAnswer")

        question_map = {}
        i = 0

        for element in question_elements:
            if not get_fields:
                value = element.get_attribute("value")
            else:
                try:
                    value = answer_elements[i]
                except IndexError:
                    self.throw(
                        "Could not find fields to input secret answers. Exiting.."
                    )

            i += 1
            question_map["question_" + str(i)] = value

        return question_map

    def submit_otp_or_answers(self, otp=None, answers=None, from_payment=False):
        if not otp and not answers:
            self.throw("Invalid response received. Exiting..")

        if otp:
            self.submit_otp(otp, from_payment)
        else:
            self.submit_answers(answers)

    def submit_otp(self, otp, from_payment):
        # There can be multiple #otpValue elements in the DOM (one hidden
        # behind the modal, one visible inside it). Pick the visible one.
        otp_field = self.br.execute_script("""
            var fields = document.querySelectorAll('#otpValue');
            for (var i = 0; i < fields.length; i++) {
                var r = fields[i].getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return fields[i];
            }
            return fields[fields.length - 1];
        """)
        otp_field.send_keys(otp)
        self.br.switch_to.default_content()
        submit_btn = self.br.execute_script("""
            var btns = document.querySelectorAll('button.bb-button-bar__button.btn-primary');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim() === 'Submit') return btns[i];
            }
            return null;
        """)
        if submit_btn:
            self.br.execute_script("arguments[0].click();", submit_btn)
        else:
            self.throw("Could not find OTP Submit button.", screenshot=True)

        # checks for proceed btn after otp submit in login workflow only
        if not from_payment:
            try:
                self.br.switch_to.default_content()
                proceed_btn = self.get_element(
                    "proceedBtn", "id", timeout=8, throw="ignore"
                )
                if proceed_btn:
                    proceed_btn.click()
                    # proceed btn prompt comes twice in the UI
                    proceed_btn = self.get_element(
                        "proceedBtn", "id", timeout=8, throw="ignore"
                    )
                    proceed_btn.click()
            except Exception:
                pass

    def submit_answers(self, answers):
        field_map = self.get_question_map(True)
        for fieldname, element in field_map.items():
            element.clear()
            element.send_keys(answers.get(fieldname))

        self.br.execute_script("return submit_challenge();")

    def continue_login(self, otp=None, answers=None):
        self.br.switch_to.default_content()
        self.submit_otp_or_answers(otp, answers)
        try:
            self.get_element(
                '//h1[@data-role="headings" and contains(@class,"bb-heading-widget__heading")]',
                "xpath",
                throw=False,
            )
        except TimeoutException:
            self.handle_login_error()
        else:
            self.login_success()

    def handle_login_error(self):
        try:
            alert = self.br.switch_to.alert.text
        except NoAlertPresentException:
            self.throw("Login failed")
        else:
            self.throw(alert)

    def login_success(self):
        self.logged_in = 1

        if self.doctype == "Bank Integration Settings":
            self.show_msg("Credentials verified successfully!")
            frappe.publish_realtime(
                "bi_action",
                {"uid": self.uid, "action": "login_success"},
                user=frappe.session.user,
                doctype=self.doctype,
                docname=self.docname,
            )
            self.logout()
        elif self.doctype == "Payment Entry":
            self.show_msg("Login Successful! Processing payment..")
            self.make_payment()
        elif self.doctype == "Bank Account":
            self.fetch_transactions()

    def logout(self):
        if self.logged_in:
            try:
                logout_btn1 = self.br.find_element(
                    By.CSS_SELECTOR,
                    'div.logout-icon-container[aria-label="Logout"][role="button"]',
                )
                self.br.execute_script("arguments[0].click();", logout_btn1)
                self.br.switch_to.default_content()
                logout_btn2 = self.br.find_element(
                    By.XPATH,
                    '//button[contains(@class,"bb-button-bar__button") and normalize-space(text())="Logout"]',
                )
                self.br.execute_script("arguments[0].click();", logout_btn2)
                time.sleep(1)
            except Exception:
                self.show_msg(
                    "We were unable to complete the logout process on the bank website. Please manually log out from your online banking account to end the session safely."
                )
        self.delete_cache()
        self.cleanup_download_dir(delete_dir=True)
        self.br.quit()

    @set_correct_payment_data
    def make_payment(self):
        self.remove_payment = False
        self.br.switch_to.default_content()
        if "/transfers/send-money" not in self.br.current_url:
            clicked = self.br.execute_script("""
                var el = document.querySelector("a[routerlink='/transfers/send-money']");
                if (el) { el.click(); return true; }
                return false;
            """)
            if not clicked:
                self.throw(
                    "Could not find the 'Send Money' navigation link. The HDFC portal layout may have changed."
                )

            self.wait_until(EC.url_contains("/transfers/send-money"))

        to_account_input_box = self.get_element("typeahead-template", "id")
        to_account_input_box.click()
        to_account_input_box.send_keys(self.data.to_account, Keys.ENTER)
        try:
            option = self.wait_until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "li.custom-to-account div.select-account-body")
                ),
                timeout=10,
            )
            option.click()
        except Exception:
            self.throw(
                "Could not find party's bank account in the list of Payees. Please add it manually"
            )

        self._select_from_account_if_needed()

        if self.data.transfer_type == "Transfer within the bank":
            self.make_payment_within_bank()
        elif self.data.transfer_type and self.data.transfer_type.startswith(
            "Transfer to other bank"
        ):
            self.make_inter_bank_payment()

    @set_correct_payment_data
    def _select_from_account_if_needed(self):
        """
        After the to-account is selected, HDFC may show an ng-select dropdown
        for the from-account if the user has child/parent accounts.
        If there is only one account (no child/parent), the website auto-sets
        the from-account and no dropdown appears.

        The dropdown has NO search input — it renders a flat list of
        div.ng-option elements each containing a
        bb-custom-product-item-basic-account-ui component.  Account numbers
        are masked (e.g. "**** **** **26 18"), so we match using the last 4
        digits of self.data.from_account.
        """
        time.sleep(1)

        from_account_selectors = self.br.find_elements(
            By.CSS_SELECTOR, 'ng-select[name="bb-custom-account-selector"]'
        )

        if not from_account_selectors:
            return

        from_account_select = from_account_selectors[0]

        already_selected = from_account_select.find_elements(
            By.CSS_SELECTOR, "div.ng-value:not(.ng-placeholder)"
        )
        if already_selected:
            selected_text = already_selected[0].text or ""
            last4 = self.data.from_account.strip().replace(" ", "")[-4:]
            if last4 and (last4 in selected_text.replace(" ", "")):
                return

        self.show_msg("Selecting from account...")

        account_stripped = self.data.from_account.strip().replace(" ", "")
        last4 = account_stripped[-4:]
        last4_spaced = last4[-4:-2] + " " + last4[-2:]

        try:
            select_container = from_account_select.find_element(
                By.CSS_SELECTOR, "div.ng-select-container"
            )
            select_container.click()
        except Exception:
            self.br.execute_script("arguments[0].click();", from_account_select)

        try:
            self.wait_until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ng-dropdown-panel div.ng-option")
                ),
                timeout=10,
            )
        except TimeoutException:
            self.throw(
                "From account selector appeared but the dropdown did not open. "
                "Please check if the HDFC portal layout has changed.",
                screenshot=True,
            )

        dropdown_options = self.br.find_elements(
            By.CSS_SELECTOR, "ng-dropdown-panel div.ng-option"
        )

        if not dropdown_options:
            self.throw(
                "From account dropdown opened but contains no options.",
                screenshot=True,
            )

        option_found = False

        for opt in dropdown_options:
            opt_text = opt.text or ""
            opt_html = opt.get_attribute("innerHTML") or ""

            if (
                last4_spaced in opt_text
                or last4 in opt_text.replace(" ", "")
                or self.data.from_account in opt_text
                or last4_spaced in opt_html
                or last4 in opt_html.replace(" ", "")
            ):
                try:
                    opt.click()
                except Exception:
                    self.br.execute_script("arguments[0].click();", opt)
                option_found = True
                break

        if not option_found:
            self.throw(
                "Could not find from-account ending in '{}' in the account selector "
                "dropdown. Please verify the account number in Bank Integration "
                "Settings.".format(last4_spaced),
                screenshot=True,
            )

        time.sleep(1)

        selected_values = from_account_select.find_elements(
            By.CSS_SELECTOR, "div.ng-value:not(.ng-placeholder)"
        )
        if not selected_values:
            self.throw(
                "From account selection did not register. "
                "The dropdown may have closed without selecting an account.",
                screenshot=True,
            )

    def _handle_post_confirm_payment_state(self):
        self.br.switch_to.default_content()

        try:
            self.wait_until(
                AnyEC(
                    EC.visibility_of_element_located(
                        (
                            By.XPATH,
                            '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]',
                        )
                    ),
                    EC.visibility_of_element_located((By.NAME, "fldAnswer")),
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, "span.success-tick")
                    ),
                ),
                throw=False,
            )
        except Exception:
            self.throw(
                "Failed to find OTP Button.",
                screenshot=True,
            )

        if (
            '//button[contains(@class, "bb-button-bar__button") and contains(@class, "btn-primary") and normalize-space(text())="Get OTP"]'
            == self.br._found_element[-1]
        ):
            self.process_otp()
        elif "fldAnswer" == self.br._found_element[-1]:
            self.process_security_questions()
        else:
            self.payment_success()

    @set_correct_payment_data
    def make_payment_within_bank(self):
        amt = self.get_element("transfer-amount-input", "id")
        amt.clear()
        amt.send_keys("%.2f" % self.data.amount)

        desc = self.get_element('input[data-role="input"]', "css_selector")
        desc.clear()
        desc.send_keys(self.data.payment_desc)

        continue_btn = self.get_element(
            'button[type="submit"].btn-primary.btn.btn-md.btn-block',
            "css_selector",
            now=True,
        )
        self.br.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", continue_btn
        )
        try:
            continue_btn.click()
        except Exception:
            self.br.execute_script("arguments[0].click();", continue_btn)

        checkbox_label = self.get_element(
            'span.bb-input-checkbox__content[data-role="checkbox-label"]',
            "css_selector",
        )
        checkbox_label.click()

        confirm_btn = self.get_element(
            'button.confirm-btn[aria-label="Confirm Transfer"]',
            "css_selector",
        )
        confirm_btn.click()
        self._handle_post_confirm_payment_state()

    @set_correct_payment_data
    def make_inter_bank_payment(self):

        amt = self.get_element("transfer-amount-input", "id")
        amt.clear()
        amt.send_keys("%.2f" % self.data.amount)

        try:
            match self.data.transfer_type:
                case "Transfer to other bank (NEFT)":
                    select_neft = self.get_element(
                        "//div[contains(@class,'transfer-mode-')][.//label[normalize-space()='NEFT']]",
                        "xpath",
                    )
                    select_neft.click()

                case "Transfer to other bank (IMPS)":
                    select_imps = self.get_element(
                        "//div[contains(@class,'transfer-mode-')][.//label[normalize-space()='IMPS']]",
                        "xpath",
                    )
                    select_imps.click()

                case "Transfer to other bank (RTGS)":
                    select_rtgs = self.get_element(
                        "//div[contains(@class,'transfer-mode-')][.//label[normalize-space()='RTGS']]",
                        "xpath",
                    )
                    select_rtgs.click()

        except Exception:
            self.throw(
                "Unable to find the payment transfer type selection buttons. "
                "The payment could not be completed, and the system logged out from the website."
            )

        desc = self.get_element('input[data-role="input"]', "css_selector")
        desc.clear()
        desc.send_keys(self.data.payment_desc)

        continue_btn = self.get_element(
            'button[type="submit"][aria-label="Continue transfer"]',
            "css_selector",
            now=True,
        )
        self.br.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", continue_btn
        )
        try:
            continue_btn.click()
        except Exception:
            self.br.execute_script("arguments[0].click();", continue_btn)

        checkbox_label = self.get_element(
            'span.bb-input-checkbox__content[data-role="checkbox-label"]',
            "css_selector",
        )
        checkbox_label.click()

        confirm_btn = self.get_element(
            'button.confirm-btn[aria-label="Confirm Transfer"]',
            "css_selector",
        )
        confirm_btn.click()
        self._handle_post_confirm_payment_state()

    def click_option(
        self, element, to_click, error=None, exact=False, compare_text=False
    ):
        for option in element.find_elements(By.TAG_NAME, "option"):
            if not compare_text:
                val = option.get_attribute("value")
            else:
                val = (option.text or "").strip()
            if not val:
                continue

            val = val.strip()

            if (exact and to_click == val) or to_click in val:
                option.click()
                break
        else:
            if error:
                self.throw(error)

    def continue_payment(self, otp=None, answers=None):
        self.br.switch_to.default_content()
        self.submit_otp_or_answers(otp, answers, from_payment=True)

        try:
            self.br.switch_to.default_content()
            self.get_element("span.success-tick", "css_selector", throw=False)

        except TimeoutException:
            self.throw(
                "We could not detect a payment success confirmation on the bank website. Please verify whether the payment went through, either directly on the bank portal or using the attached screenshot.",
                screenshot=True,
            )
        else:
            self.payment_success()

    def payment_success(self):
        self.br.switch_to.default_content()

        details_button = self.get_element("showHideBtn", "id")
        details_button.click()

        pdf_saved = False
        try:
            self.cleanup_download_dir(delete_dir=False)
            download_btn = self.br.find_element(
                By.CSS_SELECTOR,
                "button.down-btn.btn-link",
            )
            self.br.execute_script("arguments[0].click();", download_btn)
            # make sure to clear the download directory before starting a new payment in bulk payments
            filename, content = self.wait_for_download(expected_filename="transfer.pdf")
            if filename and content:
                save_file(
                    self.data.docname + " Payment Receipt.pdf",
                    content,
                    "Payment Entry",
                    self.data.docname,
                    is_private=1,
                )
                pdf_saved = True
        except Exception:
            frappe.log_error(frappe.get_traceback(), "PDF receipt download failed; falling back to screenshot")

        if not pdf_saved:
            save_file(
                self.data.docname + " Online Payment Screenshot.png",
                self.br.get_screenshot_as_png(),
                "Payment Entry",
                self.data.docname,
                is_private=1,
            )

        ref_no = "-"
        if self.data.transfer_type == "Transfer within the bank":
            try:
                ref_no = (
                    self.get_element(
                        "//div[normalize-space(text())='Transaction ID']/following-sibling::div[contains(@class,'bb-text-medium-bold')]",
                        "xpath",
                        now=True,
                        throw=False,
                    ).text
                    or "-"
                ).strip()
            except Exception:
                pass
        else:
            try:
                ref_no = (
                    self.get_element(
                        '//div[contains(@class,"bb-support--subtitle") and (contains(normalize-space(text()),"Reference") or contains(normalize-space(text()),"Transaction ID"))]/following-sibling::div[contains(@class,"bb-text-medium-bold")]',
                        "xpath",
                        throw=False,
                    ).text
                    or "-"
                ).strip()
            except Exception:
                pass

        self.remove_payment = True
        payment_entry_doc = frappe.get_doc("Payment Entry", self.data.docname)
        payment_entry_doc.online_payment_status = "Paid"
        payment_entry_doc.reference_no = ref_no
        payment_entry_doc.submit()
        frappe.db.commit()

        # these are kept separate as one requires frm object which is not present in list view
        if not self.is_bulk_payments:
            frappe.publish_realtime(
                "bi_action",
                {
                    "ref_no": ref_no,
                    "uid": self.uid,
                    "action": "payment_success",
                },
                user=frappe.session.user,
                doctype="Payment Entry",
                docname=self.data.docname,
            )
        else:
            if getattr(self, "bulk_payments", None):
                is_last = False
            else:
                is_last = True

            frappe.publish_realtime(
                "bi_action",
                {
                    "ref_no": ref_no,
                    "uid": self.uid,
                    "paid_amount": self.data.amount,
                    "docname": self.data.docname,
                    "party_name": self.data.party_name,
                    "action": "payment_success_bulk",
                    "is_last": is_last,
                },
                user=frappe.session.user,
                doctype="Payment Entry",
                docname=self.data.docname,
            )

        if self.is_bulk_payments:
            if getattr(self, "bulk_payments", None):
                send_money_btn = self.get_element(
                    "//button[normalize-space(text())='Go to Send Money' and contains(@class, 'btn-primary')]",
                    "xpath",
                    now=True,
                    throw="ignore",
                )
                if send_money_btn:
                    self.br.execute_script("arguments[0].click();", send_money_btn)
                else:
                    self.throw("Send Money button not found.")
                self.make_payment()
                return
            else:
                frappe.publish_realtime(
                    "bi_action",
                    {
                        "uid": self.uid,
                        "action": "bulk_payment_completed",
                    },
                    user=frappe.session.user,
                    doctype=self.doctype,
                    docname=self.docname,
                )

        self.logout()

    def fetch_transactions(self, from_date=None):
        def update_transactions(transactions, after_date, bank_account):
            trans_ids = frappe.get_all(
                "Bank Transaction",
                filters=[
                    ["creation", ">", add_days(after_date, -1)],
                    ["bank_account", "=", bank_account],
                ],
                fields="transaction_id",
            )
            existing_transactions = [item["transaction_id"] for item in trans_ids]
            count = 0
            closing_balance = 0
            for transaction in transactions:
                for key in ("Withdrawal", "Deposit", "Closing Balance"):
                    if transaction.get(key):
                        transaction[key] = flt(transaction[key])
                transaction["Cheque/Ref. No."] = str(
                    transaction["Cheque/Ref. No."]
                ).replace(".0", "")

                transaction_id = hashlib.sha224(str(transaction).encode()).hexdigest()

                if transaction_id in existing_transactions:
                    continue

                bank_transaction = frappe.get_doc({"doctype": "Bank Transaction"})

                bank_transaction.update(
                    {
                        "transaction_id": transaction_id,
                        "date": getdate(transaction["Date"]),
                        "description": transaction["Narration"],
                        "withdrawal": flt(transaction["Withdrawal"]),
                        "deposit": flt(transaction["Deposit"]),
                        "reference_number": transaction["Cheque/Ref. No."],
                        "closing_balance": flt(transaction["Closing Balance"]),
                        "bank_account": bank_account,
                        "unallocated_amount": abs(
                            flt(transaction["Deposit"]) - flt(transaction["Withdrawal"])
                        ),
                    }
                )
                bank_transaction.submit()
                count += 1
                closing_balance = flt(transaction["Closing Balance"])

            frappe.publish_realtime(
                "sync_transactions",
                {
                    "uid": self.uid,
                    "count": count,
                    "closing_balance": closing_balance,
                    "after_date": add_days(after_date, -1),
                },
                user=frappe.session.user,
            )

        self.switch_to_frame("main_part")
        self.switch_to_frame("left_menu")
        self.get_element("enquiryatag", selector_type="id", now=True).click()
        self.get_element("SIN_nohref", selector_type="id", now=True).click()

        self.switch_to_frame("main_part")
        self.get_element("selectselAccttype0", "id")
        self.click_option(
            self.get_element("selAccttype", now=True),
            "SCA",
            "Unable to select Account Type",
        )

        self.click_option(
            self.get_element("selAcct", now=True),
            self.data.from_account_no,
            "Please verify account number in Bank Integration Settings",
        )

        prev_valid_date = add_months(add_days(today(), -getdate().day + 1), -1)
        if not frappe.db.count(
            "Bank Transaction",
            filters={
                "bank_account": self.data.bank_account,
                "date": [">", prev_valid_date],
            },
        ):
            from_date = prev_valid_date
        else:
            from_date = frappe.get_all(
                "Bank Transaction",
                filters={"bank_account": self.data.bank_account},
                fields="date",
                order_by="creation desc",
                limit=1,
            )[0]["date"]
            if getdate(from_date) <= getdate(prev_valid_date):
                from_date = prev_valid_date
            from_date = add_days(from_date, -1)

        self.br.find_elements(By.CLASS_NAME, "radio")[1].click()

        self.get_element("frmDatePicker", selector_type="id", now=True).send_keys(
            getdate(from_date).strftime("%d/%m/%Y")
        )
        self.get_element("toDatePicker", selector_type="id", now=True).send_keys(
            getdate().strftime("%d/%m/%Y")
        )
        self.br.execute_script("return formSubmitbytype()")

        self.br.execute_script("$('.datatable').show()")
        transaction_tables = self.br.find_elements(By.CLASS_NAME, "datatable")

        if not transaction_tables:
            self.throw("No New Transactions found")
            self.logout()
            return

        transactions = _get_transactions(transaction_tables)

        self.logout()

        update_transactions(transactions, from_date, self.data.bank_account)


def _get_transactions(transaction_tables):
    from bs4 import BeautifulSoup

    transactions = []

    for table_element in transaction_tables:
        soup = BeautifulSoup(table_element.get_attribute("outerHTML"), "lxml")
        table = soup.find("table")

        if not table:
            continue

        rows = table.find_all("tr")
        if not rows:
            continue
        # First row is header
        headers = [th.text.strip() for th in rows[0].find_all("th")]

        # Remaining rows are data
        for row in rows[1:]:
            cells = row.find_all("td")

            # NOTE: Will not happen right?
            if len(cells) != len(headers):
                continue  # Skip incomplete rows

            transaction = {
                header: (cell.text.strip() or 0) for header, cell in zip(headers, cells)
            }

            transactions.append(transaction)

    transactions.reverse()  # To maintain chronological order
    return transactions
