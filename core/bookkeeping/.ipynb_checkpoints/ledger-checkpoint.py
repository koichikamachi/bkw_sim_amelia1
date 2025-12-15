#=========== bkw_sim_amelia1/core/bookkeeping/ledger.py (新規作成)

import pandas as pd
from typing import List, Dict, Any, Optional
import datetime

# 仕訳（Journal Entry）を表現するシンプルなデータクラス
# 勘定科目名は日本語のまま扱う
class JournalEntry:
    def __init__(self, date: datetime.date, account: str, amount: float, dr_cr: str, description: Optional[str] = None):
        """
        Args:
            date (datetime.date): 取引日
            account (str): 勘定科目名 (例: '現金', '建物', '初期投資長期借入金')
            amount (float): 金額 (正の値のみ)
            dr_cr (str): 借方 ('debit') または 貸方 ('credit')
            description (str): 摘要
        """
        self.date = date
        self.account = account
        self.amount = abs(amount) # 金額は常に正
        self.dr_cr = dr_cr
        self.description = description if description else f"{account}の{dr_cr}取引"

class Ledger:
    """
    全ての仕訳を保持し、DataFrameとして出力する元帳クラス。
    """
    def __init__(self):
        # 借方(Debit)と貸方(Credit)を区別して仕訳を格納
        self.entries: List[JournalEntry] = []

    def add_entry(self, entry: JournalEntry):
        """
        仕訳を元帳に追加する。
        """
        self.entries.append(entry)

    def get_df(self) -> pd.DataFrame:
        """
        格納された全ての仕訳をPandas DataFrameとして取得する。
        """
        # 仕訳リストからDataFrameを構築するためのデータリストを作成
        data: List[Dict[str, Any]] = []
        for i, entry in enumerate(self.entries):
            data.append({
                'id': i + 1,
                'date': entry.date.strftime('%Y-%m-%d'),
                'account': entry.account,
                'amount': entry.amount,
                'dr_cr': entry.dr_cr,
                'description': entry.description
            })
        
        df = pd.DataFrame(data)
        
        # 借方と貸方に分けて金額を配置
        df['debit'] = df.apply(lambda row: row['amount'] if row['dr_cr'] == 'debit' else 0, axis=1)
        df['credit'] = df.apply(lambda row: row['amount'] if row['dr_cr'] == 'credit' else 0, axis=1)
        
        # 最終的な表示項目を整える
        return df[['id', 'date', 'account', 'description', 'dr_cr', 'amount', 'debit', 'credit']]


#========= bkw_sim_amelia1/core/bookkeeping/ledger.py end