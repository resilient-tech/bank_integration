# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.contacts.doctype.contact.contact import get_default_contact

@frappe.whitelist()
def get_contact_data(party_type, party, comm_type):
    contact_name = get_default_contact(party_type, party)
    if contact_name:
        contact = frappe.get_doc('Contact', contact_name)
        if comm_type == 'Email':
            return contact.email_id
        elif comm_type == 'Mobile':
            return contact.mobile_no