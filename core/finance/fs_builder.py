# ===========================================
# core/finance/fs_builder.py
# 財務三表を Ledger から組み立てるエンジン
# ===========================================

import pandas as pd
from collections import defaultdict


class FinancialStatementBuilder:
    """
    LedgerManager の仕訳データから
    ・損益計算書（PL）
    ・貸借対照表（BS）
    ・キャッシュフロー計算（CF）
    を構築する。
    """

    def __init__(self, ledger):
        self.ledger = ledger

    # -----------------------------------------
    # 1. Ledger → DataFrame
    # -----------------------------------------
    def _load_ledger(self):
        return self.ledger.get_df().copy()

    # -----------------------------------------
    # 2. 集計ヘルパー
    # -----------------------------------------
    def _sum_dr(self, df, account):
        return df[(df["dr_cr"] == "debit") & (df["account"] == account)]["amount"].sum()

    def _sum_cr(self, df, account):
        return df[(df["dr_cr"] == "credit") & (df["account"] == account)]["amount"].sum()

    # -----------------------------------------
    # 3. PL 作成（年次）
    # -----------------------------------------
    def _build_pl(self, df):
        """
        正しい方向（行＝科目、列＝年度）で PL を作る
        """
    
        years = sorted(df["year"].unique())
    
        # PL の科目一覧（固定）
        pl_rows = [
            "売上高",
            "売上総利益",
            "販売費一般管理費",
            "建物減価償却費",
            "追加設備減価償却費",
            "租税公課（固定資産税）",
            "営業利益",
            "初期長借利息",
            "追加設備長借利息",
            "当座借越利息",
            "経常利益",
            "固定資産売却収入",
            "固定資産売却原価",
            "固定資産売却費用",
            "固定資産売却損益",
            "税引前当期利益",
            "法人税等",
            "当期利益",
        ]
    
        # 行＝科目名、列＝年度の DataFrame
        pl_df = pd.DataFrame(0.0, index=pl_rows, columns=[f"Year {y}" for y in years])
    
        for y in years:
            ydf = df[df["year"] == y]
    
            # ---- 各項目を集計 ----
            sales = self._sum_cr(ydf, "売上高")
            bld_depr = self._sum_dr(ydf, "建物減価償却費")
            add_depr = self._sum_dr(ydf, "追加設備減価償却費")
            mgmt_fee = self._sum_dr(ydf, "販売費一般管理費")
            fa_tax = self._sum_dr(ydf, "租税公課（固定資産税）")
            interest_initial = self._sum_dr(ydf, "初期長借利息")
            interest_add = self._sum_dr(ydf, "追加設備長借利息")
            interest_overdraft = self._sum_dr(ydf, "当座借越利息")
    
            disposal_income = self._sum_cr(ydf, "固定資産売却収入")
            disposal_cost = self._sum_dr(ydf, "固定資産売却原価")
            disposal_exp = self._sum_dr(ydf, "固定資産売却費用")
            disposal_profit = disposal_income - disposal_cost - disposal_exp
    
            gross_profit = sales
            operating_profit = gross_profit - mgmt_fee - bld_depr - add_depr - fa_tax
            ordinary_profit = operating_profit - interest_initial - interest_add - interest_overdraft
            pre_tax = ordinary_profit + disposal_profit
            income_tax = self._sum_dr(ydf, "法人税等")
            net_income = pre_tax - income_tax
    
            col = f"Year {y}"
    
            # ---- PL DF に書き込み ----
            pl_df.loc["売上高", col] = sales
            pl_df.loc["売上総利益", col] = gross_profit
            pl_df.loc["販売費一般管理費", col] = mgmt_fee
            pl_df.loc["建物減価償却費", col] = bld_depr
            pl_df.loc["追加設備減価償却費", col] = add_depr
            pl_df.loc["租税公課（固定資産税）", col] = fa_tax
            pl_df.loc["営業利益", col] = operating_profit
            pl_df.loc["初期長借利息", col] = interest_initial
            pl_df.loc["追加設備長借利息", col] = interest_add
            pl_df.loc["当座借越利息", col] = interest_overdraft
            pl_df.loc["経常利益", col] = ordinary_profit
            pl_df.loc["固定資産売却収入", col] = disposal_income
            pl_df.loc["固定資産売却原価", col] = disposal_cost
            pl_df.loc["固定資産売却費用", col] = disposal_exp
            pl_df.loc["固定資産売却損益", col] = disposal_profit
            pl_df.loc["税引前当期利益", col] = pre_tax
            pl_df.loc["法人税等", col] = income_tax
            pl_df.loc["当期利益", col] = net_income
    
        return pl_df
    # -----------------------------------------
    # 4. BS 作成（出口後の最終年度のみ）
    # -----------------------------------------
    def _build_bs(self, df):
        """
        Exit（売却）完了後の貸借対照表を作成する。
        → 最終年度の期末日のみで OK。
        """

        last_year = df["year"].max()
        d = df[df["year"] == last_year]

        # 資産
        cash_dr = d[(d["dr_cr"] == "debit") & (d["account"] == "預金")]["amount"].sum()
        cash_cr = d[(d["dr_cr"] == "credit") & (d["account"] == "預金")]["amount"].sum()
        cash = cash_dr - cash_cr

        # 借入金は exit_engine でゼロになる
        overdraft = 0
        loan_initial = 0
        loan_additional = 0

        # 純資産（利益剰余金）
        net_income = self._sum_cr(d, "当期利益") - self._sum_dr(d, "当期利益")

        bs_dict = {
            "預金": cash,
            "当座借越": overdraft,
            "初期投資長期借入金": loan_initial,
            "追加設備長期借入金": loan_additional,
            "純資産": net_income,
        }

        bs_df = pd.DataFrame(bs_dict, index=[f"Year {last_year}"]).T
        bs_df.index.name = "科目"
        return bs_df

    # -----------------------------------------
    # 5. CF（簡易版）
    # -----------------------------------------
    def _build_cf(self, df):
        """
        現金残高の推移から営業CF・投資CF・財務CFをざっくり計算。
        """
        cf = defaultdict(dict)
        years = sorted(df["year"].unique())

        for y in years:
            ydf = df[df["year"] == y]

            # Cash-in / Cash-out 全額集計
            cash_in = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == "預金")]["amount"].sum()
            cash_out = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "預金")]["amount"].sum()

            cf[y] = {
                "営業収支": cash_in - cash_out,
                "設備投資収支": 0,  # 今後拡張
                "財務収支": 0,
                "現金増減": cash_in - cash_out,
            }

        cf_df = pd.DataFrame(cf).T
        cf_df.index.name = "Year"
        return cf_df

    # -----------------------------------------
    # 6. 全体を組み立てる
    # -----------------------------------------
    def build(self):
        df = self._load_ledger()

        # year/month の補完
        if "date" in df.columns:
            df["year"] = pd.to_datetime(df["date"]).dt.year
            df["month"] = pd.to_datetime(df["date"]).dt.month
        else:
            df["year"] = 1
            df["month"] = 1

        pl = self._build_pl(df)
        bs = self._build_bs(df)
        cf = self._build_cf(df)

        # 簿記検証（借方＝貸方）
        debit_total = df[df["dr_cr"] == "debit"]["amount"].sum()
        credit_total = df[df["dr_cr"] == "credit"]["amount"].sum()
        is_balanced = abs(debit_total - credit_total) < 1.0

        return {
            "pl": pl,
            "bs": bs,
            "cf": cf,
            "is_balanced": is_balanced,
            "debit_total": debit_total,
            "credit_total": credit_total,
            "balance_diff": debit_total - credit_total,
        }

# ===========================================
# END fs_builder.py
# ===========================================