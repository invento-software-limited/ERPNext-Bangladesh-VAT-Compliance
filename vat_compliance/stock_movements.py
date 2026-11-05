# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Running stock balance for the Mushak 6.1 and 6.2 registers."""

from frappe.utils import flt, getdate


class RunningStock:
	"""Per-item balance carried from row to row. Each stock movement counts once, on the
	first register row dated on or after it."""

	def __init__(self, openings, movements):
		self.balances = {item: (flt(b.get("qty")), flt(b.get("value"))) for item, b in openings.items()}
		self.pending = {}
		for movement in sorted(movements, key=_posting_date):
			self.pending.setdefault(movement["item_code"], []).append(movement)

	def opening(self, item):
		return self.balances.get(item, (0.0, 0.0))

	def take_movements(self, item, upto):
		"""(qty, value) of the item's movements up to `upto` that no earlier row has counted."""
		upto = getdate(upto)
		movements = self.pending.get(item, [])
		due = [m for m in movements if getdate(m["posting_date"]) <= upto]
		self.pending[item] = movements[len(due) :]
		return sum(flt(m["qty"]) for m in due), sum(flt(m["value"]) for m in due)

	def close(self, item, qty, value):
		self.balances[item] = (qty, value)


def _posting_date(movement):
	return getdate(movement["posting_date"])
