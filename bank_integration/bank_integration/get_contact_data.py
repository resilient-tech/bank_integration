# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.contacts.doctype.contact.contact import get_default_contact

@frappe.whitelist()
def get_contact_data(party_type, party):
    if party_type != 'Employee':
        contact_name = get_default_contact(party_type, party)
        if contact_name:
            contact = frappe.get_doc('Contact', contact_name)
            return {
                'email': contact.email_id,
                'mobile': contact.mobile_no
            }
    else:
        data = frappe._dict()
        data.email, data.mobile = frappe.get_value(party_type, party,
            ('personal_email', 'cell_number'))
        return data
