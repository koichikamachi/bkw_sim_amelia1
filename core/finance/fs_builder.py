# ============================================================
# core/finance/fs_builder.py
# 仕様書 第11章 Reporting Layer 準拠版
# ============================================================

import pandas as pd


class FinancialStatementBuilder:

    def __init__(self, ledger):
        self.ledger = ledger

    # ============================================================
    # メイン：PL / BS / CF 全体を構築
    # ============================================================
    def build(self) -> dict:
        df = self.ledger.get_df().copy()

        # year列はledger.get_df()が付与済み
        years     = sorted(df["year"].dropna().unique().astype(int))
        year_cols = [f"Year {y}" for y in years]

        pl_df = self._build_pl(df, years, year_cols)
        bs_df = self._build_bs(df, years, year_cols, pl_df)
        cf_df = self._build_cf(df, years, year_cols)

        # 貸借一致チェック
        debit_total  = df[df["dr_cr"] == "debit" ]["amount"].sum()
        credit_total = df[df["dr_cr"] == "credit"]["amount"].sum()
        balance_diff = debit_total - credit_total

        return {
            "pl":           pl_df,
            "bs":           bs_df,
            "cf":           cf_df,
            "is_balanced":  abs(balance_diff) < 1.0,
            "balance_diff": abs(balance_diff),
            "debit_total":  debit_total,
            "credit_total": credit_total,
        }

    # ============================================================
    # ① 損益計算書（PL）
    # ============================================================
    def _build_pl(self, df: pd.DataFrame, years: list, year_cols: list) -> pd.DataFrame:

        pl_rows = [
            "売上高",
            "売上総利益",
            "建物減価償却費",
            "追加設備減価償却費",
            "修繕費",
            "その他販管費",
            "租税公課（消費税）",
            "固定資産税（土地）",
            "固定資産税（建物）",
            "販売費一般管理費",
            "営業利益",
            "長期借入金利息",
            "追加設備借入利息",
            "当座借越利息",
            "経常利益",
            "固定資産売却益（損）",
            "税引前当期利益",
            "所得税（法人税）",
            "当期利益",
        ]
        pl = pd.DataFrame(0.0, index=pl_rows, columns=year_cols)

        def dr(acc, ydf): return ydf[(ydf["dr_cr"] == "debit")  & (ydf["account"] == acc)]["amount"].sum()
        def cr(acc, ydf): return ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == acc)]["amount"].sum()

        for y in years:
            col = f"Year {y}"
            ydf = df[df["year"] == y]

            pl.loc["売上高",             col] = cr("売上高",             ydf)
            pl.loc["売上総利益",         col] = pl.loc["売上高", col]

            pl.loc["建物減価償却費",     col] = dr("建物減価償却費",     ydf)
            pl.loc["追加設備減価償却費", col] = dr("追加設備減価償却費", ydf)
            pl.loc["修繕費",             col] = dr("修繕費",             ydf)
            pl.loc["その他販管費",       col] = dr("その他販管費",       ydf)
            pl.loc["租税公課（消費税）", col] = dr("租税公課（消費税）", ydf)
            pl.loc["固定資産税（土地）", col] = dr("固定資産税（土地）", ydf)
            pl.loc["固定資産税（建物）", col] = dr("固定資産税（建物）", ydf)
            pl.loc["販売費一般管理費",   col] = dr("販売費一般管理費",   ydf)

            pl.loc["営業利益", col] = (
                pl.loc["売上総利益",         col]
                - pl.loc["建物減価償却費",     col]
                - pl.loc["追加設備減価償却費", col]
                - pl.loc["修繕費",             col]
                - pl.loc["その他販管費",       col]
                - pl.loc["販売費一般管理費",   col]
                - pl.loc["固定資産税（土地）", col]
                - pl.loc["固定資産税（建物）", col]
            )

            pl.loc["長期借入金利息",   col] = dr("長期借入金利息",   ydf)
            pl.loc["追加設備借入利息", col] = dr("追加設備借入利息", ydf)
            pl.loc["当座借越利息",     col] = dr("当座借越利息",     ydf)

            pl.loc["経常利益", col] = (
                pl.loc["営業利益",         col]
                - pl.loc["長期借入金利息",   col]
                - pl.loc["追加設備借入利息", col]
                - pl.loc["当座借越利息",     col]
            )

            # 売却損益（貸方残 = 益、借方残 = 損）
            gain = cr("固定資産売却益（損）", ydf)
            loss = dr("固定資産売却益（損）", ydf)
            pl.loc["固定資産売却益（損）", col] = gain - loss

            pl.loc["税引前当期利益", col] = (
                pl.loc["経常利益",             col]
                + pl.loc["固定資産売却益（損）", col]
            )

            # 所得税（法人税）：TaxEngineが借方に計上
            pl.loc["所得税（法人税）", col] = dr("所得税（法人税）", ydf)

            pl.loc["当期利益", col] = (
                pl.loc["税引前当期利益", col]
                - pl.loc["所得税（法人税）", col]
            )

        return pl

    # ============================================================
    # ② 貸借対照表（BS）
    # ============================================================
    def _build_bs(
        self,
        df: pd.DataFrame,
        years: list,
        year_cols: list,
        pl_df: pd.DataFrame,
    ) -> pd.DataFrame:

        bs_rows = [
            # 資産
            "預金",
            "未収還付消費税",
            "仮払消費税",
            "建物",
            "建物減価償却累計額",
            "追加設備",
            "追加設備減価償却累計額",
            "土地",
            "資産合計",
            # 負債
            "未払消費税",
            "未払所得税（法人税）",
            "当座借越借入金",
            "長期借入金",
            "追加設備投資借入金",
            # 純資産
            "元入金",
            "繰越利益剰余金",
            "負債・純資産合計",
        ]
        bs = pd.DataFrame(0.0, index=bs_rows, columns=year_cols)

        for y in years:
            col  = f"Year {y}"
            ydf  = df[df["year"] <= y]  # 累積

            def asset_bal(acc):
                """資産科目：借方残（dr - cr）"""
                dr = ydf[(ydf["dr_cr"] == "debit")  & (ydf["account"] == acc)]["amount"].sum()
                cr = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == acc)]["amount"].sum()
                return float(dr - cr)

            def liab_bal(acc):
                """負債・純資産科目：貸方残（cr - dr）"""
                dr = ydf[(ydf["dr_cr"] == "debit")  & (ydf["account"] == acc)]["amount"].sum()
                cr = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == acc)]["amount"].sum()
                return float(cr - dr)

            # ---- 資産 ----
            bs.loc["預金",             col] = asset_bal("預金")
            bs.loc["未収還付消費税",   col] = asset_bal("未収還付消費税")
            bs.loc["仮払消費税",       col] = asset_bal("仮払消費税")
            bs.loc["建物",             col] = asset_bal("建物")
            bs.loc["追加設備",         col] = asset_bal("追加設備")
            bs.loc["土地",             col] = asset_bal("土地")

            # 減価償却累計額：貸方残（資産のマイナス項目）→ 表示はマイナス
            bld_dep = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == "建物減価償却累計額")]["amount"].sum()
            bld_dep -= ydf[(ydf["dr_cr"] == "debit")  & (ydf["account"] == "建物減価償却累計額")]["amount"].sum()
            bs.loc["建物減価償却累計額", col] = -float(bld_dep)

            add_dep = ydf[(ydf["dr_cr"] == "credit") & (ydf["account"] == "追加設備減価償却累計額")]["amount"].sum()
            add_dep -= ydf[(ydf["dr_cr"] == "debit")  & (ydf["account"] == "追加設備減価償却累計額")]["amount"].sum()
            bs.loc["追加設備減価償却累計額", col] = -float(add_dep)

            bs.loc["資産合計", col] = (
                bs.loc["預金",                     col]
                + bs.loc["未収還付消費税",         col]
                + bs.loc["仮払消費税",             col]
                + bs.loc["建物",                   col]
                + bs.loc["建物減価償却累計額",     col]
                + bs.loc["追加設備",               col]
                + bs.loc["追加設備減価償却累計額", col]
                + bs.loc["土地",                   col]
            )

            # ---- 負債 ----
            bs.loc["未払消費税",         col] = liab_bal("未払消費税")
            bs.loc["未払所得税（法人税）", col] = liab_bal("未払所得税（法人税）")
            bs.loc["当座借越借入金",     col] = liab_bal("当座借越借入金")
            bs.loc["長期借入金",         col] = liab_bal("長期借入金")
            bs.loc["追加設備投資借入金", col] = liab_bal("追加設備投資借入金")

            # ---- 純資産 ----
            bs.loc["元入金",             col] = liab_bal("元入金")

            # 繰越利益剰余金 = 当期までの当期利益累計
            prev_cols = [f"Year {yy}" for yy in years if yy <= y]
            bs.loc["繰越利益剰余金", col] = float(pl_df.loc["当期利益", prev_cols].sum())

            bs.loc["負債・純資産合計", col] = (
                bs.loc["未払消費税",           col]
                + bs.loc["未払所得税（法人税）", col]
                + bs.loc["当座借越借入金",       col]
                + bs.loc["長期借入金",           col]
                + bs.loc["追加設備投資借入金",   col]
                + bs.loc["元入金",               col]
                + bs.loc["繰越利益剰余金",       col]
            )

        return bs

    # ============================================================
    # ③ 資金収支計算書（CF）直接法
    # ============================================================
    def _build_cf(self, df: pd.DataFrame, years: list, year_cols: list) -> pd.DataFrame:

        cf_rows = [
            "【営業収支】",
            "家賃収入（税抜）",
            "営業収入計",
            "管理費・修繕費・保険料",
            "固定資産税（土地）",
            "固定資産税（建物）",
            "未払消費税納付",
            "消費税還付受取",
            "未払所得税納付",
            "長期借入金利息",
            "追加設備借入利息",
            "当座借越利息",
            "営業支出計",
            "営業収支",
            "【設備収支】",
            "固定資産売却収入",
            "設備売却計",
            "売却費用",
            "土地購入",
            "建物購入",
            "追加設備購入",
            "設備購入計",
            "設備収支",
            "【財務収支】",
            "元入金調達",
            "長期借入金調達",
            "追加設備投資借入金調達",
            "資金調達計",
            "長期借入金返済",
            "追加設備投資借入金返済",
            "借入金返済計",
            "財務収支",
            "【資金収支尻】",
        ]
        cf = pd.DataFrame(0.0, index=cf_rows, columns=year_cols)

        # 日付を正しくパース（"2027-12-31T00:00:00.000" 形式に対応）
        df = df.copy()
        df["parsed_date"] = pd.to_datetime(df["date"])
        df["is_year_end"] = (df["parsed_date"].dt.month == 12) & (df["parsed_date"].dt.day == 31)

        def dr_sum(acc, y): return df[(df["year"] == y) & (df["dr_cr"] == "debit")  & (df["account"] == acc)]["amount"].sum()
        def cr_sum(acc, y): return df[(df["year"] == y) & (df["dr_cr"] == "credit") & (df["account"] == acc)]["amount"].sum()

        for y in years:
            col = f"Year {y}"

            # 家賃収入（税込）：売上高（税抜）+ 月次仮受消費税（年末精算12/31分を除く）
            rent_vat_monthly = float(
                df[
                    (df["year"] == y) &
                    (df["account"] == "仮受消費税") &
                    (df["dr_cr"] == "credit") &
                    ~df["is_year_end"]
                ]["amount"].sum()
            )
            cf.loc["家賃収入（税抜）", col] = cr_sum("売上高", y) + rent_vat_monthly
            cf.loc["営業収入計",       col] = cf.loc["家賃収入（税抜）", col]

            # 管理費等支出（税込）：月次仮払消費税 + 租税公課（消費税）を加算
            vat_paid_monthly = float(
                df[
                    (df["year"] == y) &
                    (df["account"] == "仮払消費税") &
                    (df["dr_cr"] == "debit") &
                    ~df["is_year_end"]
                ]["amount"].sum()
            )
            cf.loc["管理費・修繕費・保険料", col] = (
                dr_sum("販売費一般管理費", y)
                + dr_sum("修繕費",         y)
                + dr_sum("その他販管費",   y)
                + dr_sum("租税公課（消費税）", y)  # 控除不能VAT（経費化分）
                + vat_paid_monthly                 # 控除可能VAT（仮払消費税現金支出分）
            )
            cf.loc["固定資産税（土地）", col] = dr_sum("固定資産税（土地）", y)
            cf.loc["固定資産税（建物）", col] = dr_sum("固定資産税（建物）", y)
            if True:  # is_year_end列を使用
                cf.loc["未払消費税納付", col] = float(
                    df[
                        (df["year"] == y) &
                        (df["account"] == "未払消費税") &
                        (df["dr_cr"] == "debit") &
                        ~df["is_year_end"]
                    ]["amount"].sum()
                )
            else:
                cf.loc["未払消費税納付", col] = dr_sum("未払消費税", y)

            # 消費税還付受取：年末精算（12/31）以外のCr = 実際の現金還付のみ
            # （最終精算「元入金Dr/未収還付消費税Cr」は12/31・非現金のため除外）
            cf.loc["消費税還付受取", col] = float(
                df[
                    (df["year"] == y) &
                    (df["account"] == "未収還付消費税") &
                    (df["dr_cr"] == "credit") &
                    ~df["is_year_end"]
                ]["amount"].sum()
            )
            cf.loc["未払所得税納付",   col] = dr_sum("未払所得税（法人税）", y)
            cf.loc["長期借入金利息",   col] = dr_sum("長期借入金利息",       y)
            cf.loc["追加設備借入利息", col] = dr_sum("追加設備借入利息",     y)
            cf.loc["当座借越利息",     col] = dr_sum("当座借越利息",         y)

            cf.loc["営業支出計", col] = (
                cf.loc["管理費・修繕費・保険料", col]
                + cf.loc["固定資産税（土地）",   col]
                + cf.loc["固定資産税（建物）",   col]
                + cf.loc["未払消費税納付",       col]
                + cf.loc["未払所得税納付",       col]
                + cf.loc["長期借入金利息",       col]
                + cf.loc["追加設備借入利息",     col]
                + cf.loc["当座借越利息",         col]
            )
            # 消費税還付受取は営業収入として加算
            cf.loc["営業収支", col] = (
                cf.loc["営業収入計",      col]
                + cf.loc["消費税還付受取", col]
                - cf.loc["営業支出計",    col]
            )

            # 設備収支
            # 固定資産売却収入：Exit年12/31付けの預金借方合計（売却代金受取）
            cf.loc["固定資産売却収入", col] = float(
                df[
                    (df["year"] == y) &
                    df["is_year_end"] &
                    (df["account"] == "預金") &
                    (df["dr_cr"] == "debit")
                ]["amount"].sum()
            )
            cf.loc["設備売却計", col] = cf.loc["固定資産売却収入", col]
            # 売却費用：Exit年12/31付けの預金貸方から借入金返済分を除外
            exit_loan_repay_1231 = float(
                df[
                    (df["year"] == y) &
                    df["is_year_end"] &
                    (df["account"] == "長期借入金") &
                    (df["dr_cr"] == "debit")
                ]["amount"].sum()
            ) + float(
                df[
                    (df["year"] == y) &
                    df["is_year_end"] &
                    (df["account"] == "追加設備投資借入金") &
                    (df["dr_cr"] == "debit")
                ]["amount"].sum()
            )
            cf.loc["売却費用", col] = float(
                df[
                    (df["year"] == y) &
                    df["is_year_end"] &
                    (df["account"] == "預金") &
                    (df["dr_cr"] == "credit")
                ]["amount"].sum()
            ) - exit_loan_repay_1231
            # 資産取得費：借方残高＝取得年のみ発生（売却時は貸方なのでdr_sumには含まれない）
            cf.loc["土地購入",     col] = dr_sum("土地",     y)
            cf.loc["建物購入",     col] = dr_sum("建物",     y)
            cf.loc["追加設備購入", col] = dr_sum("追加設備", y)
            cf.loc["設備購入計", col] = (
                cf.loc["土地購入", col]
                + cf.loc["建物購入", col]
                + cf.loc["追加設備購入", col]
            )
            cf.loc["設備収支", col] = (
                cf.loc["設備売却計", col]
                - cf.loc["設備購入計", col]
                - cf.loc["売却費用",   col]
            )

            # 財務収支
            # 元入金調達：Exit年（最終年）の元入金増加は最終精算（非現金）なので除外
            if y == max(years):
                cf.loc["元入金調達", col] = 0.0
            else:
                cf.loc["元入金調達", col] = cr_sum("元入金", y)
            cf.loc["長期借入金調達",         col] = cr_sum("長期借入金",         y)
            cf.loc["追加設備投資借入金調達", col] = cr_sum("追加設備投資借入金", y)
            # 当座借越：毎月の補填（Cr）と返済（Dr）は現金フロー
            # Exit年12/31の「当座借越借入金Dr/元入金Cr」は非現金精算のため除外
            od_调达 = float(
                df[
                    (df["year"] == y) &
                    (df["account"] == "当座借越借入金") &
                    (df["dr_cr"] == "credit")
                ]["amount"].sum()
            )
            od_返済 = float(
                df[
                    (df["year"] == y) &
                    (df["account"] == "当座借越借入金") &
                    (df["dr_cr"] == "debit") &
                    ~df["is_year_end"]  # 12/31の元入金精算を除外
                ]["amount"].sum()
            )
            cf.loc["資金調達計", col] = (
                cf.loc["元入金調達",             col]
                + cf.loc["長期借入金調達",         col]
                + cf.loc["追加設備投資借入金調達", col]
                + od_调达
            )
            cf.loc["長期借入金返済",         col] = dr_sum("長期借入金",         y)
            cf.loc["追加設備投資借入金返済", col] = dr_sum("追加設備投資借入金", y)
            cf.loc["借入金返済計", col] = (
                cf.loc["長期借入金返済",         col]
                + cf.loc["追加設備投資借入金返済", col]
                + od_返済
            )
            cf.loc["財務収支", col] = cf.loc["資金調達計", col] - cf.loc["借入金返済計", col]

            cf.loc["【資金収支尻】", col] = (
                cf.loc["営業収支", col]
                + cf.loc["設備収支", col]
                + cf.loc["財務収支", col]
            )

        return cf

# ============================================================
# core/finance/fs_builder.py end
# ============================================================