# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import time

import frappe
import hashlib
import pandas as pd
from frappe.utils import getdate, today, add_months, add_days, flt
from frappe.utils.file_manager import save_file

from bank_integration.bank_integration.api.bank_api import BankAPI, AnyEC

# Selenium imports
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys


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

        try:
            secure_access_cb = self.get_element(
                "chkrsastu", "id", timeout=2, throw=False
            )
            secure_access_cb.click()
        except TimeoutException:
            pass

        try:
            self.get_element("fldCaptcha", timeout=1, throw=False)
        except TimeoutException:
            pass
        else:
            self.throw(
                "HDFC Netbanking is asking for a CAPTCHA, which we don't currently support. Exiting."
            )

        self.get_element("fldPassword").send_keys(self.password, Keys.ENTER)

        self.wait_until(
            AnyEC(
                EC.visibility_of_element_located(
                    (
                        By.XPATH,
                        # Message has changed on incorrect password
                        "//td/span[text()[contains(.,'Your ID and IPIN do not match. Please try again')]]",
                    )
                ),
                EC.visibility_of_element_located((By.NAME, "fldOldPass")),
                EC.visibility_of_element_located((By.NAME, "fldMobile")),
                EC.visibility_of_element_located((By.NAME, "fldAnswer")),
                EC.visibility_of_element_located((By.NAME, "common_menu1")),
            ),
            throw="ignore",
        )

        # Todo: don't think _found_element as an attribute works anymore in 4+ selenium
        if not self.br._found_element:
            self.handle_login_error()

        elif "fldOldPass" == self.br._found_element[-1]:
            self.throw(
                (
                    "The password you've set has expired. "
                    "Please set a new password manually and update the same in Bank Integration Settings."
                )
            )

        elif "is invalid" in self.br._found_element[-1]:
            self.throw(
                "The password you've set in Bank Integration Settings is incorrect."
            )

        elif "fldMobile" == self.br._found_element[-1]:
            self.process_otp()
        elif "fldAnswer" == self.br._found_element[-1]:
            self.process_security_questions()
        else:
            self.login_success()

    def process_otp(self):
        mobile_no = email_id = None
        self.get_element("fldMobile", now=True).click()

        try:
            mobile_no = self.get_element(
                '//*[@name="fldMobile"]/../following-sibling::td[last()]',
                "xpath",
                now=True,
                throw=False,
            ).text
        except NoSuchElementException:
            pass

        try:
            self.get_element("fldEmailid", now=True, throw=False).click()
            email_id = self.get_element(
                '//*[@name="fldEmailid"]/../following-sibling::td[last()]',
                "xpath",
                now=True,
                throw=False,
            ).text
        except NoSuchElementException:
            pass

        self.br.execute_script("return fireOtp();")

        frappe.publish_realtime(
            "get_bank_otp",
            {
                "mobile_no": mobile_no,
                "email_id": email_id,
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
        question_elements = self.br.find_elements_by_name("fldQuestionText")
        answer_elements = self.br.find_elements_by_name("fldAnswer")

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

    def submit_otp_or_answers(self, otp=None, answers=None):
        if not otp and not answers:
            self.throw("Invalid response received. Exiting..")

        if otp:
            self.submit_otp(otp)
        else:
            self.submit_answers(answers)

    def submit_otp(self, otp):
        otp_field = self.get_element("fldOtpToken")
        otp_field.send_keys(otp)
        self.br.execute_script("return authOtp();")

    def submit_answers(self, answers):
        field_map = self.get_question_map(True)
        for fieldname, element in field_map.items():
            element.clear()
            element.send_keys(answers.get(fieldname))

        self.br.execute_script("return submit_challenge();")

    def continue_login(self, otp=None, answers=None):
        self.submit_otp_or_answers(otp, answers)
        try:
            self.get_element("common_menu1", throw=False)
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
            self.emit_js("setTimeout(() => {frappe.hide_msgprint()}, 2000);")
            self.logout()
        elif self.doctype == "Payment Entry":
            self.show_msg("Login Successful! Processing payment..")
            self.make_payment()
        elif self.doctype == "Bank Account":
            self.fetch_transactions()

    def logout(self):
        if self.logged_in:
            self.switch_to_frame("common_menu1")
            self.br.execute_script("return Logout();")
            time.sleep(1)

        self.delete_cache()
        self.br.quit()

    def make_payment(self):
        self.switch_to_frame("common_menu1")
        self.get_element("//a[@title='Funds Transfer']", "xpath", now=True).click()

        self.switch_to_frame("main_part")
        self.get_element("selectTPT", "class_name")

        if self.data.transfer_type == "Transfer within the bank":
            self.make_payment_within_bank()
        elif self.data.transfer_type == "Transfer to other bank (NEFT)":
            self.make_neft_payment()

    def make_payment_within_bank(self):
        self.br.execute_script("return formSubmit_new('TPT');")

        self.switch_to_frame("main_part")
        self.get_element("selectselAcct0", "id")

        # from account
        from_account = self.get_element("selAcct", now=True)
        self.click_option(
            from_account,
            self.data.from_account,
            "The account number you entered in Bank Integration Settings could not be found in NetBanking",
        )

        # to account
        beneficiary = self.get_element("fldToAcct", now=True)
        self.click_option(
            beneficiary,
            self.data.to_account,
            "Unable to find a beneficiary associated with the party's account number",
        )

        # description
        desc = self.get_element("transferDtls", now=True)
        desc.clear()
        desc.send_keys(self.data.payment_desc)

        # amount
        amt = self.get_element("transferAmt", now=True)
        amt.clear()
        amt.send_keys("%.2f" % self.data.amount)

        # continue
        self.br.execute_script("return onSubmit();")

        # confirm
        self.switch_to_frame("main_part")
        self.br.execute_script("return issue_click();")

        self.switch_to_frame("main_part")

        try:
            self.wait_until(
                AnyEC(
                    EC.visibility_of_element_located((By.NAME, "fldMobile")),
                    EC.visibility_of_element_located((By.NAME, "fldAnswer")),
                    EC.visibility_of_element_located(
                        (By.XPATH, "//span[@class='successIcon']")
                    ),
                ),
                throw=False,
            )
        except:
            self.throw(
                "Failed to find indication of successful payment. Please check is payment has been processed manually.",
                screenshot=True,
            )

        if "fldMobile" == self.br._found_element[-1]:
            self.process_otp()
        elif "fldAnswer" == self.br._found_element[-1]:
            self.process_security_questions()
        else:
            self.payment_success()

    def make_neft_payment(self):
        self.br.execute_script("return formSubmit_new('NEFT');")

        self.switch_to_frame("main_part")
        self.get_element("selectselAcct0", "id")

        # from account
        from_account = self.get_element("selAcct", now=True)
        self.click_option(
            from_account,
            self.data.from_account,
            "The account number you entered in Bank Integration Settings could not be found in NetBanking",
        )

        # to account
        try:
            account_index = self.br.execute_script(
                'return l_beneacct.indexOf("{}");'.format(self.data.to_account)
            )
        except:
            self.throw("Failed to select beneficiary in Netbanking")

        if account_index == -1:
            self.throw("Beneficary account number not found in Netbanking")
        else:
            account_index = str(account_index)

        beneficiary = self.get_element("fldBeneId", now=True)
        self.click_option(
            beneficiary,
            account_index,
            "Unable to find a beneficiary associated with the party's account number",
            exact=True,
        )

        time.sleep(0.5)
        if (
            self.get_element("fldBeneAcct", now=True).get_attribute("value") or ""
        ).strip() != self.data.to_account:
            self.throw(
                "Incorrect account selected. Please contact developer for support."
            )

        # description
        desc = self.get_element("fldTxnDesc", now=True)
        desc.clear()
        desc.send_keys(self.data.payment_desc)

        # amount
        amt = self.get_element("fldTxnAmount", now=True)
        amt.clear()
        amt.send_keys("%.2f" % self.data.amount)

        # communication type
        comm_type = self.get_element("fldComMode", now=True)
        self.click_option(
            comm_type,
            self.data.comm_type,
            "Unable to select communication type in NEFT form",
            compare_text=True,
        )

        # communication value
        comm_value = self.get_element("fldMobileEmail", now=True)
        comm_value.clear()
        comm_value.send_keys(self.data.comm_value)

        # accept terms
        self.get_element(
            "//*[@name='fldtc']/preceding-sibling::span[@class='checkbox']",
            "xpath",
            now=True,
        ).click()

        # continue
        self.br.execute_script("return formSubmit();")

        # confirm
        self.switch_to_frame("main_part")
        self.br.execute_script("return formSubmit();")

        self.switch_to_frame("main_part")

        try:
            self.wait_until(
                AnyEC(
                    EC.visibility_of_element_located((By.NAME, "fldMobile")),
                    EC.visibility_of_element_located((By.NAME, "fldAnswer")),
                    EC.visibility_of_element_located(
                        (By.XPATH, "//td[contains(text(),'Reference Number')]")
                    ),
                ),
                throw=False,
            )
        except:
            self.throw(
                "Failed to find indication of successful payment. Please check is payment has been processed manually.",
                screenshot=True,
            )

        if "fldMobile" == self.br._found_element[-1]:
            self.process_otp()
        elif "fldAnswer" == self.br._found_element[-1]:
            self.process_security_questions()
        else:
            self.payment_success()

    def click_option(
        self, element, to_click, error=None, exact=False, compare_text=False
    ):
        for option in element.find_elements_by_tag_name("option"):
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
        self.switch_to_frame("main_part")
        self.submit_otp_or_answers(otp, answers)

        try:
            self.switch_to_frame("main_part")

            if self.data.transfer_type == "Transfer within the bank":
                self.get_element("//span[@class='successIcon']", "xpath", throw=False)

            elif self.data.transfer_type == "Transfer to other bank (NEFT)":
                self.get_element(
                    "//td[contains(text(),'Reference Number')]", "xpath", throw=False
                )

        except TimeoutException:
            self.throw(
                "{} authentication failed. Exiting..".format(
                    "OTP" if otp else "Security questions"
                ),
                screenshot=True,
            )
        else:
            self.payment_success()

    def payment_success(self):
        self.switch_to_frame("main_part")

        save_file(
            self.docname + " Online Payment Screenshot.png",
            self.br.get_screenshot_as_png(),
            self.doctype,
            self.docname,
            is_private=1,
        )

        ref_no = "-"
        if self.data.transfer_type == "Transfer within the bank":
            ref_no = (
                self.br.execute_script(
                    "return $('table.transTable td:nth-child(3) > span').text();"
                )
                or "-"
            )
        elif self.data.transfer_type == "Transfer to other bank (NEFT)":
            ref_no = (
                self.get_element(
                    "//td[contains(text(),'Reference Number')]/following-sibling::td[last()]",
                    "xpath",
                ).text
                or "-"
            ).strip()

        frappe.publish_realtime(
            "payment_success",
            {"ref_no": ref_no, "uid": self.uid},
            user=frappe.session.user,
            doctype="Payment Entry",
            docname=self.docname,
        )

        frappe.db.commit()
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

        self.br.find_elements_by_class_name("radio")[1].click()

        self.get_element("frmDatePicker", selector_type="id", now=True).send_keys(
            getdate(from_date).strftime("%d/%m/%Y")
        )
        self.get_element("toDatePicker", selector_type="id", now=True).send_keys(
            getdate().strftime("%d/%m/%Y")
        )
        self.br.execute_script("return formSubmitbytype()")

        transactions = []
        self.br.execute_script("$('.datatable').show()")
        transaction_tables = self.br.find_elements_by_class_name("datatable")

        if not transaction_tables:
            self.throw("No New Transactions found")
            self.logout()
            return

        for transaction_table in transaction_tables:
            transactions += pd.read_html(transaction_table.get_attribute("outerHTML"))

        self.logout()

        transactions = pd.concat(transactions)
        transactions = transactions.where(pd.notnull(transactions), None)
        transactions.fillna(0, inplace=True)
        transactions = transactions.to_dict("records")
        transactions.reverse()

        update_transactions(transactions, from_date, self.data.bank_account)
