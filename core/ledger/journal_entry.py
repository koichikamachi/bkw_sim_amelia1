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

def make_entry_pair(
    date, 
    dr_account=None, 
    cr_account=None, 
    amount=0.0, 
    description="",
    debit_account=None,
    credit_account=None
):
    """
    make_entry_pair は以下の 2 つの呼び方をサポートする：

    ① 旧仕様（positional）
        make_entry_pair(date, "現金", "売上高", 100)

    ② 新仕様（keyword）
        make_entry_pair(
            date=date,
            debit_account="現金",
            credit_account="売上高",
            amount=100
        )
    """

    # --- 新仕様 keyword を優先的に採用 ---
    if debit_account is not None:
        dr = debit_account
    else:
        dr = dr_account

    if credit_account is not None:
        cr = credit_account
    else:
        cr = cr_account

    if dr is None or cr is None:
        raise ValueError("debit_account / credit_account が指定されていません。")

    return [
        JournalEntry(
            date=date,
            description=description,
            dr_account=dr,
            dr_amount=amount,
            cr_account=cr,
            cr_amount=amount,
        )
    ]

# ================================
# END journal_entry.py  v2
# ================================