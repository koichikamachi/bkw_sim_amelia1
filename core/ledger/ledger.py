#==== bkw_sim_amelia1/core/ledger/ledger.py ====

import pandas as pd
from typing import List, Optional
from datetime import date
from .journal_entry import JournalEntry

class Ledger:
    """
    以下のコードでは、仕訳伝票 (JournalEntry) のリストを保持し、
    元帳として機能するためのメソッドを提供する。
    """
    def __init__(self):
        self.journal_entries: List[JournalEntry] = []

    def add_entry(self, entry: JournalEntry):
        """仕訳を追加する"""
        self.journal_entries.append(entry)

    def clear(self):
        """仕訳帳をクリアする"""
        self.journal_entries = []

    def get_df(self) -> pd.DataFrame:
        """仕訳帳の全エントリを DataFrame として返す"""
        return pd.DataFrame([vars(e) for e in self.journal_entries])

    # ★ NEW METHOD: 勘定残高の取得 ★
    def get_balance(self, account: str, date: Optional[date] = None) -> float:
        """
        指定された日付時点、または全期間の、指定された勘定科目の残高を取得する。
        残高 = 借方合計 - 貸方合計
        """
        balance = 0.0
        
        for entry in self.journal_entries:
            # 1. 指定日以前の仕訳のみを対象とする
            if date is not None and entry.date > date:
                continue
            
            # 2. 指定された勘定科目の仕訳のみを対象とする
            if entry.account != account:
                continue
            
            # 3. 残高を計算する (借方加算、貸方減算)
            if entry.dr_cr == "debit":
                balance += entry.amount
            elif entry.dr_cr == "credit":
                balance -= entry.amount
                
        return balance
#======= 以上, core/ledger/ledger.py end ======