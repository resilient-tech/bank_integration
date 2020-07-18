# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import time

import frappe
from frappe.utils.file_manager import save_file

import bank_integration
from bank_integration.bank_integration.api.bank_api import BankAPI, AnyEC

# Selenium imports
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoAlertPresentException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys

class HDFCBankAPI(BankAPI):
    def init(self):
        self.bank_name = 'HDFC Bank'

    def login(self):
        self.show_msg('Attempting login...')
        self.setup_browser()
        self.br.get('https://netbanking.hdfcbank.com/netbanking/')

        self.switch_to_frame('login_page')
        cust_id = self.get_element('fldLoginUserId')
        cust_id.send_keys(self.username, Keys.ENTER)

        self.get_element('chkrsastu', 'id').click()

        try:
            self.get_element('fldCaptcha', timeout=1, throw=False)
        except TimeoutException:
            pass
        else:
            self.throw('HDFC Netbanking is asking for a CAPTCHA, which we don\'t currently support. Exiting.')

        pass_input = self.get_element('fldPassword')
        pass_input.send_keys(self.password, Keys.ENTER)

        self.wait_until(AnyEC(
            EC.visibility_of_element_located((By.XPATH,
                "//td/span[text()[contains(.,'The Customer ID/IPIN (Password) is invalid.')]]")),
            EC.visibility_of_element_located((By.NAME, 'fldOldPass')),
            EC.visibility_of_element_located((By.NAME, 'fldMobile')),
            EC.visibility_of_element_located((By.NAME, 'common_menu1'))
        ), throw='ignore')

        if not self.br._found_element:
            self.handle_login_error()

        elif 'fldOldPass' == self.br._found_element[-1]:
            self.throw(('The password you\'ve set has expired. '
                'Please set a new password manually and update the same in Bank Integration Settings.'))

        elif 'is invalid' in self.br._found_element[-1]:
            self.throw('The password you\'ve set in Bank Integration Settings is incorrect.')

        elif 'fldMobile' == self.br._found_element[-1]:
            self.process_otp()
        else:
            self.login_success()

    def process_otp(self):
        mobile_no = email_id = None
        self.get_element('fldMobile', now=True).click()

        try:
            mobile_no = self.get_element('//*[@name="fldMobile"]/../following-sibling::td[last()]', 'xpath',
                now=True, throw=False).text
        except NoSuchElementException:
            pass

        try:
            self.get_element('fldEmailid', now=True, throw=False).click()
            email_id = self.get_element('//*[@name="fldEmailid"]/../following-sibling::td[last()]', 'xpath',
                now=True, throw=False).text
        except NoSuchElementException:
            pass

        self.br.execute_script('return fireOtp();')

        frappe.publish_realtime('get_bank_otp', {
            'mobile_no': mobile_no,
            'email_id': email_id,
            'uid': self.uid,
            'bank_name': self.bank_name,
            'resume_info': self.get_resume_info(),
            'data': self.data,
            'logged_in': self.logged_in
        }, user=frappe.session.user, doctype=self.doctype, docname=self.docname)

        setattr(bank_integration, self.uid, self)

    def submit_otp(self, otp):
        otp_field = self.get_element('fldOtpToken')
        otp_field.send_keys(otp)
        self.br.execute_script('return authOtp();')

    def continue_login(self, otp):
        self.submit_otp(otp)
        try:
            self.get_element('common_menu1', throw=False)
        except TimeoutException:
            self.handle_login_error()
        else:
            self.login_success()

    def handle_login_error(self):
        try:
            alert = self.br.switch_to.alert.text
        except NoAlertPresentException:
            self.throw('Login failed')
        else:
            self.throw(alert)

    def login_success(self):
        self.logged_in = True

        if self.doctype == 'Bank Integration Settings':
            self.show_msg('Credentials verified successfully!')
            self.emit_js("setTimeout(() => {frappe.hide_msgprint()}, 2000);")
            self.logout()
        elif self.doctype == 'Payment Entry':
            self.show_msg('Login Successful! Processing payment..')
            self.make_payment()

    def logout(self):
        if self.logged_in:
            self.switch_to_frame('common_menu1')
            self.br.execute_script('return Logout();')
            time.sleep(1)

        self.br.quit()

        if self.uid and hasattr(bank_integration, self.uid):
            delattr(bank_integration, self.uid)

    def make_payment(self):
        self.switch_to_frame('common_menu1')
        self.get_element("//a[@title='Funds Transfer']", 'xpath', now=True).click()

        self.switch_to_frame('main_part')

        if self.data.transfer_type == 'Transfer within the bank':
            self.make_payment_within_bank()
        elif self.data.transfer_type == 'Transfer to other bank (NEFT)':
            self.make_neft_payment()

    def make_payment_within_bank(self):
        self.get_element('selectTPT', 'class_name')
        self.br.execute_script("return formSubmit_new('TPT');")

        self.switch_to_frame('main_part')
        self.get_element('frmTxn')

        # from account
        from_account = self.get_element('selAcct', now=True)
        self.click_option(from_account, self.data.from_account,
            'The account number you entered in Bank Integration Settings could not be found in NetBanking')

        # to account
        beneficiary = self.get_element('fldToAcct', now=True)
        self.click_option(beneficiary, self.data.to_account,
            'Unable to find a beneficiary associated with the party\'s account number')

        # description
        desc = self.get_element('transferDtls', now=True)
        desc.clear()
        desc.send_keys(self.data.payment_desc)

        # amount
        amt = self.get_element('transferAmt', now=True)
        amt.clear()
        amt.send_keys('%.2f' % self.data.amount)

        # continue
        self.br.execute_script("return onSubmit();")

        # confirm
        self.switch_to_frame('main_part')
        self.br.execute_script("return issue_click();")

        self.switch_to_frame('main_part')

        self.wait_until(AnyEC(
            EC.visibility_of_element_located((By.NAME, 'fldMobile')),
            EC.visibility_of_element_located((By.XPATH, "//span[@class='successIcon']"))
        ))

        if 'fldMobile' == self.br._found_element[-1]:
            self.process_otp()
        else:
            self.payment_success()

    def click_option(self, element, to_click, error=None):
        for option in element.find_elements_by_tag_name('option'):
            val = option.get_attribute('value')
            if not val:
                continue

            if to_click in val:
                option.click()
                break
        else:
            if error:
                self.throw(error)

    def make_neft_payment(self):
        pass

    def continue_payment(self, otp):
        self.switch_to_frame('main_part')
        self.submit_otp(otp)

        try:
            self.switch_to_frame('main_part')

            if self.data.transfer_type == 'Transfer within the bank':
                self.get_element("//span[@class='successIcon']", 'xpath', throw=False)
        except TimeoutException:
            self.throw('OTP Authentication failed. Exiting..')
        else:
            self.payment_success()

    def payment_success(self):
        self.switch_to_frame('main_part')

        save_file(self.docname + ' Online Payment Screenshot.png', self.br.get_screenshot_as_png(), self.doctype,
            self.docname, is_private=1)

        ref_no = '-'
        if self.data.transfer_type == 'Transfer within the bank':
            ref_no = self.br.execute_script("return $('table.transTable td:nth-child(3) > span').text();") or '-'

        frappe.publish_realtime('payment_success', {'ref_no': ref_no, 'uid': self.uid},
            user=frappe.session.user, doctype="Payment Entry", docname=self.docname)

        frappe.db.commit()
        self.logout()
