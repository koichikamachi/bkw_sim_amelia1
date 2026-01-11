# ====================
#    bkw_sim_amelia1/core/ledger/journal_entry.py  v.01
# ====================

from dataclasses import dataclass
from datetime import date

@dataclass
class JournalEntry:
    """
    1つの取引（仕訳）を表現するデータクラス
    仕様書 に基づく
    """
    date: date          # 取引日
    description: str    # 摘要（メモ）
    dr_account: str     # 借方科目
    dr_amount: float    # 借方金額
    cr_account: str     # 貸方科目
    cr_amount: float    # 貸方金額

    def __post_init__(self):
        # 簡易的なバリデーション: 貸借金額は一致しているべき（浮動小数点の誤差は別途考慮）
        if abs(self.dr_amount - self.cr_amount) > 1.0:
            # 警告を出すかエラーにするかは設計次第だが、一旦printで警告
            print(f"Warning: Unbalanced entry created: {self.description}")

# =============================
# 仕訳生成ユーティリティ
# =============================

def make_entry_pair(date, dr_account, cr_account, amount, description=""):
    """
    借方・貸方の JournalEntry をまとめて返すユーティリティ。
    """
    return [
        JournalEntry(
            date=date,
            dr_account=dr_account,
            cr_account=cr_account,
            dr_amount=amount,
            cr_amount=0.0,
            description=description
        ),
        JournalEntry(
            date=date,
            dr_account=cr_account,
            cr_account=dr_account,
            dr_amount=0.0,
            cr_amount=amount,
            description=description
        )
    ]

# ========== bkw_sim_amelia1/core/ledger/journal_entry.py  v.01 end