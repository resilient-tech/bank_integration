# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from bank_integration.bank_integration.api import get_bank_api

class BankIntegrationSettings(Document):
	def validate(self):
		if not self.disabled:
			frappe.emit_js("frappe.msgprint('Checking credentials');",
			doctype=self.doctype, docname=self.name)

			bank = get_bank_api(self.bank_name, self.username, self.bank_account_no)
			bank.login(self.password)

			frappe.emit_js("frappe.update_msgprint('Logging in...');",
			doctype=self.doctype, docname=self.name)

			bank.check_login(logout=True)

			frappe.emit_js("frappe.update_msgprint('Credentials verified successfully!'); \
			setTimeout(() => {frappe.hide_msgprint()}, 2000);",
			doctype=self.doctype, docname=self.name)