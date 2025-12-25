#============== core/reporting/ledger_to_pl.py

import pandas as pd
from .ledger_mapping import PL_MAPPING

def ledger_to_pl(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ledger → PL（年次）
    """
    rows = {}

    for _, row in ledger_df.iterrows():
        year = row["year"]
        account = row["dr_account"] or row["cr_account"]
        amount = row["amount"]

        if account not in PL_MAPPING:
            continue

        pl_item = PL_MAPPING[account]

        if year not in rows:
            rows[year] = {}

        rows[year].setdefault(pl_item, 0.0)

        # 借方はマイナス、貸方はプラス
        if row["cr_account"] == account:
            rows[year][pl_item] += amount
        else:
            rows[year][pl_item] -= amount

    df = pd.DataFrame(rows).fillna(0).T
    df.index.name = "Year"
    return df

# ============== end core/reporting/ledger_to_pl.py