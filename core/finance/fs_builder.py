# ============================================================
# core/finance/fs_builder.py
# 財務三表（PL / BS / CF）自動生成エンジン（完全版）
# ============================================================
import streamlit as st
print("### LOADED FS_BUILDER:", __file__)
import pandas as pd


class FinancialStatementBuilder:

    def __init__(self, ledger):
        self.ledger = ledger

    # ============================================================
    # メイン：PL / BS / CF 全体を構築
    # ============================================================
    def build(self):
        df = self.ledger.get_df().copy()

        # デバッグ
        st.write("COLUMNS:", df.columns)
        st.write("DATE HEAD:", df["date"].head())
        st.write("DATE DTYPE:", df["date"].dtype)

        # 年度生成
        df["year"] = df["date"].dt.year
        years = sorted(df["year"].unique())
        year_cols = [f"Year {y}" for y in years]

        st.write("YEARS:", years)
        st.write("YEAR_COLS:", year_cols)

        # ============================================================
        # ① 損益計算書（PL）
        # ============================================================
        pl_rows = [
            "売上高",
            "仕入",
            "売上総利益",
            "建物減価償却費",
            "追加設備減価償却費",
            "租税公課（消費税）",
            "租税公課（固定資産税）",
            "販売費一般管理費",
            "営業利益",
            "当座借越利息",
            "初期長借利息",
            "追加設備長借利息",
            "運転資金借入金利息",
            "その他営業外費用",
            "経常利益",
            "特別利益",
            "税引前当期利益",
            "所得税",
            "当期利益",
        ]
        pl_df = pd.DataFrame(0.0, index=pl_rows, columns=year_cols)

        for y in years:
            col = f"Year {y}"
            ydf = df[df["year"] == y]

            # 収益
            pl_df.loc["売上高", col] = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == "売上高")]["amount"].sum()

            # 仕入
            pl_df.loc["仕入", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "仕入")]["amount"].sum()

            # 粗利
            pl_df.loc["売上総利益", col] = pl_df.loc["売上高", col] - pl_df.loc["仕入", col]

            # 減価償却費
            pl_df.loc["建物減価償却費", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "建物減価償却費")]["amount"].sum()
            pl_df.loc["追加設備減価償却費", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "追加設備減価償却費")]["amount"].sum()

            # 税金
            pl_df.loc["租税公課（固定資産税）", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "租税公課（固定資産税）")]["amount"].sum()
            pl_df.loc["租税公課（消費税）", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "租税公課（消費税）")]["amount"].sum()

            # 管理費
            pl_df.loc["販売費一般管理費", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "販売費一般管理費")]["amount"].sum()

            # 営業利益
            pl_df.loc["営業利益", col] = (
                pl_df.loc["売上総利益", col]
                - pl_df.loc["建物減価償却費", col]
                - pl_df.loc["追加設備減価償却費", col]
                - pl_df.loc["販売費一般管理費", col]
                - pl_df.loc["租税公課（固定資産税）", col]
            )

            # 営業外費用
            for acc in ["当座借越利息", "初期長借利息", "追加設備長借利息", "運転資金借入金利息", "その他営業外費用"]:
                pl_df.loc[acc, col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == acc)]["amount"].sum()

            # 経常利益
            pl_df.loc["経常利益", col] = (
                pl_df.loc["営業利益", col]
                - pl_df.loc["当座借越利息", col]
                - pl_df.loc["初期長借利息", col]
                - pl_df.loc["追加設備長借利息", col]
                - pl_df.loc["運転資金借入金利息", col]
                - pl_df.loc["その他営業外費用", col]
            )

            # 特別利益
            pl_df.loc["特別利益", col] = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == "特別利益")]["amount"].sum()

            # 税引前利益
            pl_df.loc["税引前当期利益", col] = pl_df.loc["経常利益", col] + pl_df.loc["特別利益", col]

            # 所得税
            pl_df.loc["所得税", col] = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == "所得税")]["amount"].sum()

            # 当期利益
            pl_df.loc["当期利益", col] = pl_df.loc["税引前当期利益", col] - pl_df.loc["所得税", col]

        # ============================================================
        # ② 貸借対照表（BS）
        # ============================================================
        bs_rows = [
            "預金",
            "売掛金",
            "仮払消費税",
            "建物",
            "建物減価償却累計額",
            "追加設備",
            "追加設備減価償却累計額",
            "土地",
            "資産合計",
            "買掛金",
            "未払消費税",
            "未払所得税",
            "仮受消費税",
            "当座借越",
            "初期投資長期借入金",
            "追加設備長期借入金",
            "運転資金借入金",
            "繰越利益剰余金",
            "元入金",
            "負債・元入金合計",
        ]
        bs_df = pd.DataFrame(0.0, index=bs_rows, columns=year_cols)

        for y in years:
            col = f"Year {y}"
            ydf = df[df["year"] <= y]

            def bal(acc):
                dr = ydf[(ydf["dr_cr"] == "debit") & (ydf["account"] == acc)]["amount"].sum()
                cr = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == acc)]["amount"].sum()
                return dr - cr

            # 個別資産負債
            for acc in bs_rows:
                if acc in ["資産合計", "負債・元入金合計"]:
                    continue
                bs_df.loc[acc, col] = bal(acc)

            # 繰越利益剰余金
            prev_cols = [f"Year {yy}" for yy in years if yy <= y]
            bs_df.loc["繰越利益剰余金", col] = pl_df.loc["当期利益", prev_cols].sum()

            # 資産合計
            bs_df.loc["資産合計", col] = (
                bs_df.loc["預金", col]
                + bs_df.loc["売掛金", col]
                + bs_df.loc["仮払消費税", col]
                + bs_df.loc["建物", col]
                + bs_df.loc["追加設備", col]
                + bs_df.loc["土地", col]
            )

            # 負債＋元入金合計
            bs_df.loc["負債・元入金合計", col] = (
                bs_df.loc["買掛金", col]
                + bs_df.loc["未払消費税", col]
                + bs_df.loc["未払所得税", col]
                + bs_df.loc["仮受消費税", col]
                + bs_df.loc["当座借越", col]
                + bs_df.loc["初期投資長期借入金", col]
                + bs_df.loc["追加設備長期借入金", col]
                + bs_df.loc["運転資金借入金", col]
                + bs_df.loc["元入金", col]
                + bs_df.loc["繰越利益剰余金", col]
            )

        # ============================================================
        # ③ 資金収支計算書（CF）
        # ============================================================

        cf_rows = [
            "【営業収支】",
            "預金売上",
            "売掛金入金",
            "営業収入計",
            "販売費一般管理費",
            "固定資産税",
            "未払消費税納付",
            "未払所得税納付",
            "当座借越利息",
            "初期長借利息",
            "追加設備長借利息",
            "運転資金借入金利息",
            "営業支出計",
            "営業収支",
            "【設備収支】",
            "土地売却",
            "建物・追加設備売却",
            "設備売却計",
            "売却費用",
            "土地購入",
            "建物購入",
            "追加設備購入",
            "設備購入計",
            "設備収支",
            "【財務収支】",
            "元入金",
            "当座借越",
            "初期投資長期借入金",
            "追加設備長期借入金",
            "運転資金借入金",
            "資金調達計",
            "当座借越返済",
            "初期投資長期借入金返済",
            "追加設備長借入金返済",
            "運転資金借入金返済",
            "借入金返済計",
            "財務収支",
            "【資金収支尻】",
        ]
        cf_df = pd.DataFrame(0.0, index=cf_rows, columns=year_cols)

        def cf_in(acc, y):
            return df[(df["year"] == y) & (df["dr_cr"] == "credit") & (df["account"] == acc)]["amount"].sum()

        def cf_out(acc, y):
            return df[(df["year"] == y) & (df["dr_cr"] == "debit") & (df["account"] == acc)]["amount"].sum()

        for y in years:
            col = f"Year {y}"

            # 営業収入
            cf_df.loc["預金売上", col] = cf_in("売上高", y)
            cf_df.loc["売掛金入金", col] = cf_in("売掛金", y)
            cf_df.loc["営業収入計", col] = cf_df.loc["預金売上", col] + cf_df.loc["売掛金入金", col]

            # 営業支出
            for acc in [
                "販売費一般管理費",
                "租税公課（固定資産税）",
                "未払消費税",
                "未払所得税",
                "当座借越利息",
                "初期長借利息",
                "追加設備長借利息",
                "運転資金借入金利息",
            ]:
                cf_df.loc[acc.replace("租税公課（固定資産税）", "固定資産税")
                              .replace("未払消費税", "未払消費税納付")
                              .replace("未払所得税", "未払所得税納付"),
                          col] = cf_out(acc, y)

            cf_df.loc["営業支出計", col] = (
                cf_df.loc["販売費一般管理費", col]
                + cf_df.loc["固定資産税", col]
                + cf_df.loc["未払消費税納付", col]
                + cf_df.loc["未払所得税納付", col]
                + cf_df.loc["当座借越利息", col]
                + cf_df.loc["初期長借利息", col]
                + cf_df.loc["追加設備長借利息", col]
                + cf_df.loc["運転資金借入金利息", col]
            )

            cf_df.loc["営業収支", col] = cf_df.loc["営業収入計", col] - cf_df.loc["営業支出計", col]

            # 設備売却（新仕様）
            cf_df.loc["土地売却", col] = cf_in("土地売却収入", y)
            cf_df.loc["建物・追加設備売却", col] = cf_in("建物・追加設備売却収入", y)

            cf_df.loc["設備売却計", col] = (
                cf_df.loc["土地売却", col]
                + cf_df.loc["建物・追加設備売却", col]
            )

            cf_df.loc["売却費用", col] = cf_out("売却費用", y)

            # 設備購入
            cf_df.loc["土地購入", col] = cf_out("土地", y)
            cf_df.loc["建物購入", col] = cf_out("建物", y)
            cf_df.loc["追加設備購入", col] = cf_out("追加設備", y)
            cf_df.loc["設備購入計", col] = (
                cf_df.loc["土地購入", col]
                + cf_df.loc["建物購入", col]
                + cf_df.loc["追加設備購入", col]
            )

            cf_df.loc["設備収支", col] = (
                cf_df.loc["設備売却計", col]
                - cf_df.loc["設備購入計", col]
                - cf_df.loc["売却費用", col]
            )

            # 財務収支：借入
            for acc in [
                "元入金",
                "当座借越",
                "初期投資長期借入金",
                "追加設備長期借入金",
                "運転資金借入金",
            ]:
                cf_df.loc[acc, col] = cf_in(acc, y)

            cf_df.loc["資金調達計", col] = (
                cf_df.loc["元入金", col]
                + cf_df.loc["当座借越", col]
                + cf_df.loc["初期投資長期借入金", col]
                + cf_df.loc["追加設備長期借入金", col]
                + cf_df.loc["運転資金借入金", col]
            )

            # 借入返済
            cf_df.loc["当座借越返済", col] = cf_out("当座借越", y)
            cf_df.loc["初期投資長期借入金返済", col] = cf_out("初期投資長期借入金", y)
            cf_df.loc["追加設備長借入金返済", col] = cf_out("追加設備長期借入金", y)
            cf_df.loc["運転資金借入金返済", col] = cf_out("運転資金借入金", y)

            cf_df.loc["借入金返済計", col] = (
                cf_df.loc["当座借越返済", col]
                + cf_df.loc["初期投資長期借入金返済", col]
                + cf_df.loc["追加設備長借入金返済", col]
                + cf_df.loc["運転資金借入金返済", col]
            )

            cf_df.loc["財務収支", col] = cf_df.loc["資金調達計", col] - cf_df.loc["借入金返済計", col]

            # 最終資金収支
            cf_df.loc["【資金収支尻】", col] = (
                cf_df.loc["営業収支", col]
                + cf_df.loc["設備収支", col]
                + cf_df.loc["財務収支", col]
            )

        # ============================================================
        # 貸借一致チェック
        # ============================================================
        debit_total = df[(df["dr_cr"] == "debit")]["amount"].sum()
        credit_total = df[(df["dr_cr"] == "credit")]["amount"].sum()
        balance_diff = debit_total - credit_total
        is_balanced = abs(balance_diff) < 1.0

        # ============================================================
        # 返却
        # ============================================================
        return {
            "pl": pl_df,
            "bs": bs_df,
            "cf": cf_df,
            "is_balanced": is_balanced,
            "balance_diff": balance_diff,
            "debit_total": debit_total,
            "credit_total": credit_total,
        }

# ============================================================
# end
# ============================================================