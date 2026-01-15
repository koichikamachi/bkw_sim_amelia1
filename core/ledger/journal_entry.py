# ================================
# core/ledger/journal_entry.py  v2
# ================================

from dataclasses import dataclass
from datetime import date


@dataclass
class JournalEntry:
    """
    bkw_sim における「1つの仕訳」を正確に表すデータ構造。

    ・借方（dr_account, dr_amount）
    ・貸方（cr_account, cr_amount）

    ※ 借方と貸方を *1つの JournalEntry にまとめる* のが設計の基本。
      LedgerManager.get_df() は JournalEntry 1件から
      借方行・貸方行の 2行を生成する。
    """

    date: date          # 仕訳日
    description: str    # 摘要
    dr_account: str     # 借方科目
    dr_amount: float    # 借方金額
    cr_account: str     # 貸方科目
    cr_amount: float    # 貸方金額

    def __post_init__(self):
        # 借方と貸方の一致チェック（許容誤差 ±1.0円）
        if abs(self.dr_amount - self.cr_amount) > 1.0:
            print(
                f"Warning: Unbalanced JournalEntry on {self.date}: "
                f"{self.dr_account} {self.dr_amount} / "
                f"{self.cr_account} {self.cr_amount}  ({self.description})"
            )


# =======================================
# 仕訳生成ユーティリティ（正式版）
# =======================================

def make_entry_pair(date, dr_account, cr_account, amount, description=""):
    """
    正しい形の仕訳（JournalEntry）を 1 件返す。

    例：
        現金 100 / 売上高 100

    LedgerManager に渡すと DataFrame では 2 行に展開される。
    """
    return [
        JournalEntry(
            date=date,
            description=description,
            dr_account=dr_account,
            dr_amount=amount,
            cr_account=cr_account,
            cr_amount=amount,
        )
    ]


# ================================
# END journal_entry.py  v2
# ================================