# ===============================
# core/ledger/ledger.py
# ===============================

import pandas as pd
from core.ledger.journal_entry import JournalEntry


class LedgerManager:
    """
    LedgerManager
    --------------
    ・JournalEntry をそのまま受け取り
    ・内部に時系列で蓄積し
    ・勘定科目別残高などの台帳集計を行い
    ・DataFrame として吐き出す
    """

    def __init__(self):
        # JournalEntry のリスト
        self.entries: list[JournalEntry] = []

    # -------------------------------------------------
    # JournalEntry 追加
    # -------------------------------------------------
    def add_entry(self, entry: JournalEntry):
        """
        JournalEntry を1件追加する
        """
        if not isinstance(entry, JournalEntry):
            raise TypeError(
                f"LedgerManager.add_entry expects JournalEntry, got {type(entry)}"
            )

        self.entries.append(entry)

    # -------------------------------------------------
    # 勘定科目別残高取得
    # （借方＋ / 貸方−）
    # -------------------------------------------------
    def get_account_balance(self, account_name: str) -> float:
        """
        指定した勘定科目の残高を返す
        当座借越・現金残高チェック等で使用
        """
        balance = 0.0

        for e in self.entries:
            if e.dr_account == account_name:
                balance += e.dr_amount
            if e.cr_account == account_name:
                balance -= e.cr_amount

        return balance

    # -------------------------------------------------
    # Ledger → DataFrame 変換
    # -------------------------------------------------
    def get_df(self) -> pd.DataFrame:
        """
        Ledger に溜まった JournalEntry を
        表示・集計用の DataFrame に変換する
        """
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
                "description": e.description
            })
            entry_id += 1

            # 貸方
            rows.append({
                "id": entry_id,
                "date": e.date,
                "account": e.cr_account,
                "dr_cr": "credit",
                "amount": e.cr_amount,
                "description": e.description
            })
            entry_id += 1

        df = pd.DataFrame(rows)
        return df