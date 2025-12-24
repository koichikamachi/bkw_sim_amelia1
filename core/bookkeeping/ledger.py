# =============================== core/ledger/ledger.py

import pandas as pd

class LedgerManager:
    def __init__(self):
        self.entries = []

    def add_entry(self, year, dr_account, cr_account, amount, description=""):
        if amount == 0:
            return
        self.entries.append({
            "year": year,
            "dr_account": dr_account,
            "cr_account": cr_account,
            "amount": amount,
            "description": description
        })

    def get_ledger_df(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame(
                columns=["year", "dr_account", "cr_account", "amount", "description"]
            )
        return pd.DataFrame(self.entries)