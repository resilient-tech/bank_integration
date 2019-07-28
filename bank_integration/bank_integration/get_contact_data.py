# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.contacts.doctype.contact.contact import get_default_contact

@frappe.whitelist()
def get_contact_data(party_type, party, comm_type):
    if party_type != 'Employee':
        contact_name = get_default_contact(party_type, party)
        if contact_name:
            contact = frappe.get_doc('Contact', contact_name)
            if comm_type == 'Email':
                return contact.email_id
            elif comm_type == 'Mobile':
                return contact.mobile_no
    else:
        if comm_type == 'Email':
            return frappe.get_value(party_type, party, 'personal_email')
        elif comm_type == 'Mobile':
            return frappe.get_value(party_type, party, 'cell_number')
