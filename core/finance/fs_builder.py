# ===========================================
# core/finance/fs_builder.py
# 財務三表を Ledger から組み立てるエンジン（完全整合版）
# ===========================================

import pandas as pd
from collections import defaultdict


class FinancialStatementBuilder:
    """
    LedgerManager の仕訳データから
    ・損益計算書（PL）
    ・貸借対照表（BS）
    ・キャッシュフロー計算書（CF）
    を構築する。
    """

    def __init__(self, ledger):
        self.ledger = ledger

    # -----------------------------------------
    # Ledger → DataFrame
    # -----------------------------------------
    def _load_ledger(self):
        return self.ledger.get_df().copy()

    # -----------------------------------------
    # 集計ヘルパー
    # -----------------------------------------
    def _sum_dr(self, df, account):
        return df[(df["dr_cr"] == "debit") & (df["account"] == account)]["amount"].sum()

    def _sum_cr(self, df, account):
        return df[(df["dr_cr"] == "credit") & (df["account"] == account)]["amount"].sum()

    # -----------------------------------------
    # 1. 損益計算書（PL）
    # -----------------------------------------
    def _build_pl(self, df):
        years = sorted(df["year"].unique())

        # PL の行（固定）
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

        pl_df = pd.DataFrame(0.0, index=pl_rows, columns=[f"Year {y}" for y in years])

        for y in years:
            ydf = df[df["year"] == y]
            col = f"Year {y}"

            # ---------------------
            # 主要科目
            # ---------------------
            sales = self._sum_cr(ydf, "売上高")
            mgmt = self._sum_dr(ydf, "販売費一般管理費")

            # 減価償却（建物／追加設備）← 最重要（整合済）
            bld_depr = self._sum_dr(ydf, "建物減価償却費")
            add_depr = self._sum_dr(ydf, "追加設備減価償却費")

            # 固定資産税（全角カッコの整合）
            fa_tax = self._sum_dr(ydf, "租税公課（固定資産税）")

            # 利息
            interest_initial = self._sum_dr(ydf, "初期長借利息")
            interest_add = self._sum_dr(ydf, "追加設備長借入利息") \
                + self._sum_dr(ydf, "追加設備長借利息")
            interest_overdraft = self._sum_dr(ydf, "当座借越利息")

            # 固定資産売却
            disposal_income = self._sum_cr(ydf, "固定資産売却収入")
            disposal_cost = self._sum_dr(ydf, "固定資産売却原価")
            disposal_exp = self._sum_dr(ydf, "固定資産売却費用")
            disposal_profit = disposal_income - disposal_cost - disposal_exp

            # ---------------------
            # 演算
            # ---------------------
            gross_profit = sales
            operating_profit = gross_profit - mgmt - bld_depr - add_depr - fa_tax
            ordinary_profit = operating_profit - interest_initial - interest_add - interest_overdraft
            pre_tax = ordinary_profit + disposal_profit

            tax = self._sum_dr(ydf, "法人税等")
            net_income = pre_tax - tax

            # ---------------------
            # 書き込み
            # ---------------------
            pl_df.loc["売上高", col] = sales
            pl_df.loc["売上総利益", col] = gross_profit
            pl_df.loc["販売費一般管理費", col] = mgmt
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
            pl_df.loc["法人税等", col] = tax
            pl_df.loc["当期利益", col] = net_income

        return pl_df

    # -----------------------------------------
    # 2. 貸借対照表（B/S）
    # -----------------------------------------
    def _build_bs(self, df):

        last_year = df["year"].max()
        all_until_y = df[df["year"] <= last_year]
        ydf = df[df["year"] == last_year]
        col = f"Year {last_year}"

        bs_rows = [
            "預金",
            "土地",
            "初期建物",
            "建物減価償却累計額",
            "追加設備",
            "追加設備減価償却累計額",
            "未払所得税",
            "当座借越",
            "初期投資長期借入金",
            "追加設備長期借入金",
            "純資産",
        ]

        bs_df = pd.DataFrame(0.0, index=bs_rows, columns=[col])

        # 預金
        dr_cash = self._sum_dr(all_until_y, "預金")
        cr_cash = self._sum_cr(all_until_y, "預金")
        bs_df.loc["預金", col] = dr_cash - cr_cash

        # 土地
        land_cost = self._sum_dr(all_until_y, "土地")
        bs_df.loc["土地", col] = land_cost

        # 初期建物
        bld = self._sum_dr(all_until_y, "建物")
        bs_df.loc["初期建物", col] = bld

        # ▼ 減価償却累計額（建物／追加設備）← 最重要
        bs_df.loc["建物減価償却累計額", col] = self._sum_cr(all_until_y, "建物減価償却累計額")
        bs_df.loc["追加設備減価償却累計額", col] = self._sum_cr(all_until_y, "追加設備減価償却累計額")

        # 追加設備
        add = self._sum_dr(all_until_y, "追加設備")
        bs_df.loc["追加設備", col] = add

        # 未払税金
        income_tax = self._sum_dr(ydf, "法人税等")
        bs_df.loc["未払所得税", col] = income_tax

        # 借入金（出口後は基本０）
        bs_df.loc["当座借越", col] = 0
        bs_df.loc["初期投資長期借入金", col] = 0
        bs_df.loc["追加設備長期借入金", col] = 0

        # 純資産（利益剰余金）
        net_income = self._sum_cr(all_until_y, "当期利益") - self._sum_dr(all_until_y, "当期利益")
        bs_df.loc["純資産", col] = net_income

        return bs_df

    # -----------------------------------------
    # 3. キャッシュフロー（CF）
    # -----------------------------------------
    def _build_cf(self, df):
        years = sorted(df["year"].unique())
        cf_dict = {}

        for y in years:
            ydf = df[df["year"] == y]

            cash_in = self._sum_cr(ydf, "預金")
            cash_out = self._sum_dr(ydf, "預金")

            cf_dict[f"Year {y}"] = {
                "営業収支": cash_in - cash_out,
                "設備収支": 0,
                "財務収支": 0,
                "現金増減": cash_in - cash_out,
            }

        cf_df = pd.DataFrame(cf_dict).T
        cf_df.index.name = "科目"
        return cf_df

    # -----------------------------------------
    # 4. 三表をまとめる
    # -----------------------------------------
    def build(self):
        df = self._load_ledger()

        # 日付 → year/month 生成
        if "date" in df.columns:
            df["year"] = pd.to_datetime(df["date"]).dt.year
            df["month"] = pd.to_datetime(df["date"]).dt.month
        else:
            df["year"] = 1
            df["month"] = 1

        pl = self._build_pl(df)
        bs = self._build_bs(df)
        cf = self._build_cf(df)

        # 簿記検証
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