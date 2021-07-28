# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import add_days


def reconcile_with_payment_entries(transaction, account):
    transaction = frappe._dict(transaction)

    filters = {
        "docstatus": 1,
        "reference_no": ["Like", "%" + transaction.reference_number.lstrip("0")],
        "reference_date": [
            "Between",
            [
                add_days(transaction.date, -7),
                add_days(transaction.date, 1),
            ],
        ],
        "ifnull(clearance_date, '')": "",
    }

    if transaction.withdrawal > 0:
        filters["paid_from"] = account
        filters["paid_amount"] = transaction.withdrawal
    elif transaction.deposit > 0:
        filters["paid_to"] = account
        filters["paid_amount"] = transaction.deposit

    payment_entry = frappe.get_all(
        "Payment Entry",
        filters=filters,
        fields=["name", "paid_amount"],
    )

    if len(payment_entry) != 1:
        return 0

    transaction_doc = frappe.get_doc("Bank Transaction", transaction.name)

    transaction_doc.append(
        "payment_entries",
        {
            "payment_document": "Payment Entry",
            "payment_entry": payment_entry[0].name,
            "allocated_amount": payment_entry[0].paid_amount,
        },
    )
    transaction_doc.save(ignore_permissions=True)
    transaction_doc.update_allocations()

    return 1


def reconcile_with_journal_entries(transaction, account):
    journal_entries = frappe.get_all(
        "Journal Entry",
        filters={
            "docstatus": 1,
            "cheque_no": ["Like", "%" + transaction.reference_number.lstrip("0")],
            "cheque_date": [
                "Between",
                [
                    add_days(transaction.date, -7),
                    add_days(transaction.date, 1),
                ],
            ],
            "ifnull(clearance_date, '')": "",
        },
        fields=["name", "'Journal Entry' as doctype"],
    )

    for journal_entry in journal_entries:
        filters = {
            "parenttype": journal_entry["doctype"],
            "parent": journal_entry["name"],
            "account": account,
        }
        if transaction.withdrawal > 0:
            filters["credit_in_account_currency"] = transaction.withdrawal
        else:
            filters["debit_in_account_currency"] = transaction.deposit
        journal_entry_account = frappe.get_all(
            "Journal Entry Account",
            filters=filters,
        )
        if not journal_entry_account:
            continue
        else:
            transaction_doc = frappe.get_doc("Bank Transaction", transaction.name)

            transaction_doc.append(
                "payment_entries",
                {
                    "payment_document": "Journal Entry",
                    "payment_entry": journal_entry["name"],
                    "allocated_amount": transaction.withdrawal
                    if transaction.withdrawal > 0
                    else transaction.deposit,
                },
            )
            transaction_doc.save(ignore_permissions=True)
            transaction_doc.update_allocations()

            return 1
    return 0


@frappe.whitelist()
def reconcile_transactions(uid, bank_account):
    account = frappe.get_value("Bank Account", bank_account, "account")
    transactions = frappe.get_all(
        "Bank Transaction",
        filters={
            "docstatus": 1,
            "unallocated_amount": [">", "0"],
            "bank_account": bank_account,
            "ifnull(reference_number, '')": ("!=", ""),
        },
        fields=["name", "withdrawal", "deposit", "reference_number", "date"],
    )

    count = 0

    for transaction in transactions:
        if reconcile_with_payment_entries(transaction, account):
            count += 1
        elif reconcile_with_journal_entries(transaction, account):
            count += 1

    frappe.publish_realtime(
        "auto_reconcile",
        {
            "uid": uid,
            "count": count,
        },
        user=frappe.session.user,
    )
