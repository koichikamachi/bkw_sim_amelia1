import pandas as pd

class LedgerManager:
    def __init__(self):
        """
        仕訳データを一括管理するクラス。
        bkw_sim_amelia1/core/ledger/ 配下に位置し、全モジュールから参照される「記録帳」の役割。
        """
        self.entries = []

    # =============================================================
    # 純粋に仕訳データをリストに追加する
    # =============================================================
    def add_entry(self, year: int, dr_account: str, cr_account: str, amount: float, description: str = ""):
        if amount == 0:
            return
            
        self.entries.append({
            "year": year,
            "dr_account": dr_account,
            "cr_account": cr_account,
            "amount": amount,
            "description": description
        })

    # =============================================================
    # 記録されたデータをDataFrameで返す
    # =============================================================
    def get_ledger_df(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame(columns=["year", "dr_account", "cr_account", "amount", "description"])
        df = pd.DataFrame(self.entries)
        df['debit'] = df['amount']
        df['credit'] = df['amount']
        return df

# =================== bkw_sim_amelia1/core/ledger/ledger.py end