# ===============================
# core/ledger/ledger.py（完全整合版260110）
# ===============================

import pandas as pd
from core.ledger.journal_entry import JournalEntry, make_entry_pair

class LedgerManager:
    """
    LedgerManager（統合版）
    -----------------------
    ・JournalEntry の蓄積
    ・減価償却ユニットの登録
    ・ローンユニットの登録
    ・月次・年次集計に必要なデータ構造を全て保持
    """

    def __init__(self):
        # 仕訳（JournalEntry）のリスト
        self.entries: list[JournalEntry] = []

        # 減価償却ユニット
        self.depreciation_units = []

        # 借入金ユニット
        self.loan_units = []

    # -------------------------------------------------
    # 仕訳1件追加
    # -------------------------------------------------
    def add_entry(self, entry: JournalEntry):
        if not isinstance(entry, JournalEntry):
            raise TypeError(
                f"LedgerManager.add_entry expects JournalEntry, got {type(entry)}"
            )
        self.entries.append(entry)

    # -------------------------------------------------
    # 仕訳複数追加（InitialEntryGenerator で使用）
    # -------------------------------------------------
    def add_entries(self, entries: list[JournalEntry]):
        for e in entries:
            self.add_entry(e)

    # -------------------------------------------------
    # 減価償却ユニット登録
    # -------------------------------------------------
    def register_depreciation_unit(self, unit):
        """MonthlyEntryGenerator で使うために登録"""
        self.depreciation_units.append(unit)

    # -------------------------------------------------
    # 借入金ユニット登録
    # -------------------------------------------------
    def register_loan_unit(self, unit):
        """返済スケジュール作成のために登録"""
        self.loan_units.append(unit)

    # -------------------------------------------------
    # 勘定科目の残高取得
    # -------------------------------------------------
    def get_account_balance(self, account_name: str) -> float:
        balance = 0.0
        for e in self.entries:
            if e.dr_account == account_name:
                balance += e.dr_amount
            if e.cr_account == account_name:
                balance -= e.cr_amount
        return balance

    # -------------------------------------------------
    # Ledger → DataFrame
    # -------------------------------------------------
    def get_df(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame(
                columns=["id", "date", "account", "dr_cr", "amount", "description"]
            )

        rows = []
        entry_id = 1

        for e in self.entries:
            # 借方
            rows.append({
                "id": entry_id,
                "date": e.date,
                "account": e.dr_account,
                "dr_cr": "debit",
                "amount": e.dr_amount,
                "description": e.description,
            })
            entry_id += 1

            # 貸方
            rows.append({
                "id": entry_id,
                "date": e.date,
                "account": e.cr_account,
                "dr_cr": "credit",
                "amount": e.cr_amount,
                "description": e.description,
            })
            entry_id += 1

        return pd.DataFrame(rows)
    # -------------------------------------------------
    # 減価償却ユニットの取得
    # -------------------------------------------------
    def get_all_depreciation_units(self):
        return self.depreciation_units

    # -------------------------------------------------
    # 借入金ユニットの取得
    # -------------------------------------------------
    def get_all_loan_units(self):
        return self.loan_units

# ===============================
# END core/ledger/ledger.py
# ===============================