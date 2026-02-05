# ===============================
# core/ledger/ledger.py（完全修正版）
# ===============================

import pandas as pd
from core.ledger.journal_entry import JournalEntry, make_entry_pair

class LedgerManager:

    def __init__(self):
        self.entries = []
        self.depreciation_units = []
        self.loan_units = []

    # -----------------------------------------
    # 仕訳追加
    # -----------------------------------------
    def add_entry(self, entry: JournalEntry):
        if not isinstance(entry, JournalEntry):
            raise TypeError(f"LedgerManager.add_entry expects JournalEntry, got {type(entry)}")
        self.entries.append(entry)

    def add_entries(self, entries):
        for e in entries:
            self.add_entry(e)

    # -----------------------------------------
    # 減価償却ユニット
    # -----------------------------------------
    def register_depreciation_unit(self, unit):
        self.depreciation_units.append(unit)

    def get_depreciation_units(self):
        return self.depreciation_units

    # -----------------------------------------
    # 借入ユニット
    # -----------------------------------------
    def register_loan_unit(self, unit):
        self.loan_units.append(unit)

    def get_loan_units(self):
        return self.loan_units

    # -----------------------------------------
    # 勘定科目残高
    # -----------------------------------------
    def get_account_balance(self, account_name: str):
        balance = 0.0
        for e in self.entries:
            if e.dr_account == account_name:
                balance += e.dr_amount
            if e.cr_account == account_name:
                balance -= e.cr_amount
        return balance

    # -----------------------------------------
    # DataFrame 変換
    # -----------------------------------------
    def get_df(self):
        if not self.entries:
            return pd.DataFrame(columns=["id", "date", "account", "dr_cr", "amount", "description"])

        rows = []
        eid = 1

        for e in self.entries:
            rows.append({
                "id": eid,
                "date": e.date,
                "account": e.dr_account,
                "dr_cr": "debit",
                "amount": e.dr_amount,
                "description": e.description
            })
            eid += 1

            rows.append({
                "id": eid,
                "date": e.date,
                "account": e.cr_account,
                "dr_cr": "credit",
                "amount": e.cr_amount,
                "description": e.description
            })
            eid += 1

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

# ===============================
# END
# ===============================