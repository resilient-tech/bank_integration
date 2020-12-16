# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import add_days


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
        fields=["name", "debit", "credit", "reference_number", "date"],
    )

    count = 0

    for transaction in transactions:
        transaction = frappe._dict(transaction)

        filters = {
            "docstatus": 1,
            "reference_no": transaction.reference_number.lstrip("0"),
            "reference_date": [
                "Between",
                [
                    add_days(transaction.date, -7),
                    add_days(transaction.date, 1),
                ],
            ],
            "ifnull(clearance_date, '')": "",
        }

        if transaction.debit > 0:
            filters["paid_from"] = account
            filters["paid_amount"] = transaction.debit
        elif transaction.credit > 0:
            filters["paid_to"] = account
            filters["paid_amount"] = transaction.credit

        payment_entry = frappe.get_all(
            "Payment Entry",
            filters=filters,
            fields=["name", "paid_amount"],
        )

        if not payment_entry:
            journal_entries = frappe.get_all(
                "Journal Entry",
                filters=[
                    {
                        "docstatus": 1,
                        "cheque_no": transaction.reference_number.lstrip("0"),
                        "cheque_date": [
                            "Between",
                            [
                                add_days(transaction.date, -7),
                                add_days(transaction.date, 1),
                            ],
                        ],
                    },
                    ["ifnull(clearance_date, '')", "=", ""],
                ],
                fields=["name", "'Journal Entry' as doctype"],
            )

            for journal_entry in journal_entries:
                filters = {
                    "parenttype": journal_entry["doctype"],
                    "parent": journal_entry["name"],
                    "account": account,
                }
                if transaction.debit > 0:
                    filters["credit_in_account_currency"] = transaction.debit
                else:
                    filters["debit_in_account_currency"] = transaction.credit
                journal_entry_account = frappe.get_all(
                    "Journal Entry Account",
                    filters=filters,
                )
                if journal_entry_account:
                    transaction_doc = frappe.get_doc(
                        "Bank Transaction", transaction.name
                    )

                    transaction_doc.append(
                        "payment_entries",
                        {
                            "payment_document": "Journal Entry",
                            "payment_entry": journal_entry["name"],
                            "allocated_amount": transaction.debit
                            if transaction.debit > 0
                            else transaction.credit,
                        },
                    )
                    transaction_doc.save(ignore_permissions=True)
                    transaction_doc.update_allocations()

                    count += 1
                    break

        if len(payment_entry) != 1:
            continue

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

        count += 1

    frappe.publish_realtime(
        "auto_reconcile",
        {
            "uid": uid,
            "count": count,
        },
        user=frappe.session.user,
    )