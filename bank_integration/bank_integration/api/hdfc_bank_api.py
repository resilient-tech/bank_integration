# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.file_manager import save_file

from bank_integration.bank_integration.api.bank_api import BankAPI, AnyEC

# Selenium imports
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, NoAlertPresentException

class HDFCBankAPI(BankAPI):
    def __init__(self, username, account_no):
        super(HDFCBankAPI, self).__init__(username, account_no)

    def login(self, password):
        self.setup_browser()
        self.br.get('https://mobilebanking.hdfcbank.com/mobilebanking/')

        cust_id = WebDriverWait(self.br, self.timeout).until(
            EC.visibility_of_element_located((By.NAME, 'fldLoginUserId'))
        )
        cust_id.send_keys(self.username)
        cust_id.submit()

        pass_input = WebDriverWait(self.br, self.timeout).until(
            EC.visibility_of_element_located((By.ID, 'upass'))
        )
        pass_input.send_keys(password)

        try:
            self.br.find_element_by_id('chkLogin').click()
        except NoSuchElementException:
            pass

        pass_input.submit()

    def logout(self):
        WebDriverWait(self.br, self.timeout).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'logoutIco'))
        ).click()

        self.br.quit()
        if hasattr(self, 'payment_uid'):
            frappe._bank_session.pop(self.payment_uid, None)

    def check_login(self, logout=False):
        WebDriverWait(self.br, self.timeout).until(AnyEC(
            EC.alert_is_present(),
            EC.visibility_of_element_located((By.CLASS_NAME, 'logoutIco'))
        ))

        try:
            alert = self.br.switch_to.alert.text
        except NoAlertPresentException:
            pass
        else:
            self.throw(alert)

        if logout:
            self.logout()

    def make_payment(self, to_account, transfer_type, amount, payment_desc,
    docname, payment_uid, comm_type='None', comm_value='None'):
        WebDriverWait(self.br, self.timeout).until(EC.visibility_of_element_located(
            (By.PARTIAL_LINK_TEXT, 'Third Party Transfer')
            )).find_element_by_tag_name('div').click()

        self.docname = docname
        self.payment_uid = payment_uid
        self.transfer_type = transfer_type
        if transfer_type == 'Transfer within the bank':
            self.make_payment_within_bank(to_account, amount, payment_desc)
        elif transfer_type == 'Transfer to other bank (NEFT)':
            self.make_neft_payment(to_account, amount, payment_desc, comm_type, comm_value)

    def make_payment_within_bank(self, to_account, amount, payment_desc):

        WebDriverWait(self.br, self.timeout).until(EC.visibility_of_element_located(
            (By.PARTIAL_LINK_TEXT, 'Transfer within the bank')
            )).find_element_by_tag_name('div').click()

        # Select from account
        from_account = WebDriverWait(self.br, self.timeout).until(
            EC.visibility_of_element_located((By.ID, 'fldFromAcctNo')))

        for option in from_account.find_elements_by_tag_name('option'):
            if self.account_no in option.get_attribute('value'):
                option.click()
                break
        else:
            self.throw('The account number you entered in Bank Integration Settings is incorrect', logout=True)

        # Select party account
        beneficiary = self.br.find_element_by_id('fldToAcctNo')
        for option in beneficiary.find_elements_by_tag_name('option'):
            if to_account in option.get_attribute('value'):
                option.click()
                break
        else:
            self.throw('Unable to find a beneficiary associated with the party\'s account number', logout=True)

        self.br.find_element_by_id('fldTxnDesc').send_keys(payment_desc)
        self.br.find_element_by_id('fldTxnAmount').send_keys(str(amount))
        self.br.find_element_by_name('fldContinue').click()
        self.continue_payment()

    def continue_payment(self):
        # Click confirm button
        WebDriverWait(self.br, self.timeout).until(EC.visibility_of_element_located(
            (By.NAME, 'fldConfirm'))).click()

        WebDriverWait(self.br, self.timeout).until(AnyEC(
            EC.visibility_of_element_located((By.NAME, 'fldOtp')),
            EC.visibility_of_element_located((By.ID, 'impssuccess'))
        ))

        if not self.br._found_element:
            self.throw('Timed out waiting for element to be present', logout=True)


        if 'fldOtp' in self.br._found_element:
            WebDriverWait(self.br, self.timeout).until(
                EC.visibility_of_element_located((By.NAME, 'fldMobile'))).click()

            mobile_no = WebDriverWait(self.br, self.timeout).until(
                EC.visibility_of_element_located((By.ID, 'usrMobileNo'))).text

            self.br.find_element_by_name('fldOtp').click()

            if not hasattr(frappe, '_bank_session'):
                frappe._bank_session = {self.payment_uid: self}
            else:
                if not isinstance(frappe._bank_session, dict):
                    frappe._bank_session = {}

                frappe._bank_session[self.payment_uid] = self

            frappe.publish_realtime('get_otp',
                {'mobile_no': mobile_no, 'payment_uid': self.payment_uid},
                user=frappe.session.user, doctype="Payment Entry",
                docname=self.docname)

        elif 'impssuccess' in self.br._found_element:
            self.payment_success_action()


    def continue_payment_with_otp(self, otp):
        WebDriverWait(self.br, self.timeout).until(EC.visibility_of_element_located(
            (By.ID, 'fldOtpToken'))).send_keys(otp)
        self.br.find_element_by_name('fldOtpAuth').click()

        WebDriverWait(self.br, self.timeout).until(AnyEC(
            EC.visibility_of_element_located((By.CLASS_NAME, 'rsaAuthFailure')),
            EC.visibility_of_element_located((By.ID, 'impssuccess'))
        ))

        if not self.br._found_element:
            self.throw('Timed out waiting for element to be present', logout=True)

        if 'rsaAuthFailure' in self.br._found_element:
            self.throw('OTP Authentication has failed. Please try again.', logout=True)

        else:
            self.payment_success_action()

    def payment_success_action(self):
        # Get reference no. and screenshot << refno is the id
        save_file(
            self.docname + ' Online Payment Screenshot.png',
            self.br.get_screenshot_as_png(), 'Payment Entry',
            self.docname, is_private=1
        )

        if self.transfer_type == 'Transfer within the bank':
            ref_no = self.br.find_element_by_id('refno').text
        else:
            ref_no = self.br.find_element_by_class_name('clsreferenceno').text

        frappe.publish_realtime('payment_success',
            {'ref_no': ref_no, 'payment_uid': self.payment_uid},
            user=frappe.session.user, doctype="Payment Entry", docname=self.docname)

        self.logout()


    def make_neft_payment(self, to_account, amount, payment_desc, comm_type, comm_value):
        WebDriverWait(self.br, self.timeout).until(EC.visibility_of_element_located(
            (By.PARTIAL_LINK_TEXT, 'Transfer to other bank')
            )).find_element_by_tag_name('div').click()

        # Select from account
        try:
            from_account = WebDriverWait(self.br, self.timeout).until(
                EC.visibility_of_element_located((By.ID, 'fldAcctNo')))
        except:
            self.throw('Unable to access NEFT services at the moment. Please try again later.', logout=True)

        for option in from_account.find_elements_by_tag_name('option'):
            if self.account_no in option.get_attribute('value'):
                option.click()
                break
        else:
            self.throw('The account number you entered in Bank Integration Settings is incorrect', logout=True)

        # Select party account
        beneficiary = self.br.find_element_by_id('fldBenefDetail')
        for option in beneficiary.find_elements_by_tag_name('option'):
            if to_account in option.get_attribute('value'):
                option.click()
                break
        else:
            self.throw('Unable to find a beneficiary associated with the party\'s account number', logout=True)

        self.br.find_element_by_id('fldTxnDesc').send_keys(payment_desc)
        self.br.find_element_by_id('fldTxnAmount').send_keys(str(amount))

        comm_mode = self.br.find_element_by_id('fldComMode')
        for option in comm_mode.find_elements_by_tag_name('option'):
            if comm_type in option.text:
                option.click()
                break

        self.br.find_element_by_id('fldMobileEmail').send_keys(comm_value)

        continue_btns = self.br.find_elements_by_name("fldContinue")
        for x in continue_btns:
            if x.is_displayed():
                x.click()
                break


        WebDriverWait(self.br, self.timeout).until(AnyEC(
            EC.alert_is_present(),
            EC.visibility_of_element_located((By.NAME, 'fldConfirm'))
        ))

        if self.br._found_element == 'alert':
            self.br.switch_to.alert.accept()

        self.continue_payment()