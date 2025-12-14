#==== bkw_sim_amelia1/core/ledger/journal_entry.py ====

from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass
class JournalEntry:
    """
    以下のコードでは、一つの仕訳伝票の基本情報を定義している。
    """
    date: date
    description: str
    account: str
    amount: float
    dr_cr: Literal["debit", "credit"]
    category: Literal["BS", "PL", "CF"]
    # ★ 修正点: month_index を追加！
    month_index: int = 0  # 0: 初期投資, 1~N*12: 月次処理

#======= 以上, core/ledger/journal_entry.py end ======