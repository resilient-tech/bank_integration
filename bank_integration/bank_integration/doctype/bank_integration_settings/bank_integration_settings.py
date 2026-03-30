# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from bank_integration.bank_integration.api import get_bank_api

class BankIntegrationSettings(Document):
	def before_save(self):
		filters = {"bank_account_no": self.bank_account_no}
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		bank_integrations=frappe.db.get_list(
			'Bank Integration Settings',
			fields=['name'],
			filters=filters,
			)
		if len(bank_integrations) > 0:
			frappe.throw('Only one Bank Integration for a bank account can exist.')

	@frappe.whitelist()
	def check_credentials(self, uid):
		if self.disabled:
			return

		bank = get_bank_api(self.bank_name, self.username, self.get_password(), doctype=self.doctype, docname=self.name,
			uid=uid)