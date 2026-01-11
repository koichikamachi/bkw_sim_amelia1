# ===== core/bookkeeping/journal_entry.py =====

from dataclasses import dataclass
from datetime import date

@dataclass
class JournalEntry:
    """
    仕訳レンガ（JournalEntry）
    ---------------------------
    ・1つの仕訳を表現する最小単位
    ・LedgerManager がこれを受け取って集計する
    """
    date: date
    account: str
    dr_cr: str   # "debit" or "credit"
    amount: float

    def to_dict(self) -> dict:
        """LedgerManager で扱いやすい辞書形式に変換する。"""
        return {
            "date": self.date,
            "account": self.account,
            "dr_cr": self.dr_cr,
            "amount": self.amount,
        }


def make_entry_pair(date, debit_account, credit_account, amount):
    """
    借方と貸方を同時に生成するユーティリティ。
    """
    return [
        JournalEntry(date, debit_account, "debit", amount),
        JournalEntry(date, credit_account, "credit", amount),
    ]

# ===== end journal_entry.py =====