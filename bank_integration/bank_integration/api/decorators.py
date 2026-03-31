from frappe import _dict
from functools import wraps

def set_correct_payment_data(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, "bulk_payments", None):
            if self.remove_payment:
                data = _dict(self.bulk_payments.pop(0))
            else:
                data = self.data
        else:
            data = getattr(self, "data", None)

        if not data:
            self.throw("No payment data available")

        self.data = data
        self.docname = data.docname

        return func(self, *args, **kwargs)

    return wrapper
