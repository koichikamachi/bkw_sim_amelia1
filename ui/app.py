# ============== bkw_sim_amelia1/ui/app.py ==============

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import traceback
import sys
import os
from typing import Optional, List
from io import BytesIO

# ----------------------------------------------------------------------
# パス解決
# ----------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# ✅ V12標準インポート
from config.params import (
    SimulationParams,
    LoanParams,
    ExitParams,
    AdditionalInvestmentParams,
)
from core.simulation.simulation import Simulation

# ----------------------------------------------------------------------
# 1. 表示用DataFrame生成
# ----------------------------------------------------------------------
def create_display_dataframes(fs_data: dict) -> dict:
    display_dfs = {}

    def format_cell(val):
        if pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
            return ""
        if isinstance(val, (int, float, np.integer, np.floating)):
            try:
                return f"{int(round(val)):,}"
            except Exception:
                return str(val)
        return str(val)

    for key in ["pl", "bs", "cf"]:
        if key in fs_data:
            df = fs_data[key].copy()
            df_display = df.reset_index() if df.index.name == "科目" else df.copy()
            num_cols = [c for c in df_display.columns if c.startswith("Year")]
            for col in num_cols:
                df_display[col] = df_display[col].apply(format_cell)
            if "科目" in df_display.columns:
                df_display = df_display.set_index("科目")
            display_dfs[key] = df_display

    return display_dfs

# ----------------------------------------------------------------------
# 2. 財務諸表組み立て（V12 ledger_df 対応版）
# ----------------------------------------------------------------------
def create_financial_statements(ledger_df: pd.DataFrame, holding_years: int) -> dict:
    years_list = list(range(1, holding_years + 1))
    year_index_labels = [f"Year {y}" for y in years_list]

    # V12形式対応：dr_cr + account → 仮想カラム生成
    if ledger_df is not None and not ledger_df.empty:
        ledger_df = ledger_df.copy()

        ledger_df["dr_account"] = np.where(
            ledger_df["dr_cr"] == "debit",
            ledger_df.get("account", ""),
            "",
        )
        ledger_df["cr_account"] = np.where(
            ledger_df["dr_cr"] == "credit",
            ledger_df.get("account", ""),
            "",
        )
        ledger_df["debit_amount"] = np.where(
            ledger_df["dr_cr"] == "debit",
            ledger_df["amount"],
            0,
        )
        ledger_df["credit_amount"] = np.where(
            ledger_df["dr_cr"] == "credit",
            ledger_df["amount"],
            0,
        )

        debit_total = ledger_df["debit_amount"].sum()
        credit_total = ledger_df["credit_amount"].sum()
    else:
        debit_total = credit_total = 0.0

    balance_diff = abs(debit_total - credit_total)
    is_balanced = balance_diff < 1.0

    def make_fs_df(rows):
        df = pd.DataFrame(0.0, index=rows, columns=year_index_labels).astype("Float64")
        df.index.name = "科目"
        return df

    # 科目定義
    pl_rows = [
        "売上高",
        "売上総利益",
        "建物減価償却費",
        "追加設備減価償却費",
        "租税公課（消費税)",
        "租税公課（固定資産税)",
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

    bs_rows = [
        "預金",
        "初期建物",
        "建物減価償却累計額",
        "追加設備",
        "追加設備減価償却累計額",
        "土地",
        "資産合計",
        "未払所得税",
        "当座借越",
        "初期投資長期借入金",
        "追加設備長期借入金",
        "運転資金借入金",
        "繰越利益剰余金",
        "元入金",
        "負債・元入金合計",
    ]

    cf_rows = [
        "【営業収支】",
        "現金売上",
        "営業収入計",
        "現金仕入",
        "固定資産税",
        "販売費一般管理費",
        "未払消費税納付",
        "未払所得税納付",
        "当座借越利息",
        "初期長借利息",
        "追加設備長期借入金利息",
        "運転資金借入金利息",
        "その他営業外費用",
        "営業支出計",
        "営業収支",
        "【設備収支】",
        "土地・建物・追加設備売却",
        "設備売却計",
        "売却費用",
        "土地購入",
        "初期建物購入",
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
        "追加設備長期借入金返済",
        "運転資金借入金返済",
        "借入金返済計",
        "財務収支",
        "【資金収支尻】",
    ]

    pl_df = make_fs_df(pl_rows)
    bs_df = make_fs_df(bs_rows)
    cf_df = make_fs_df(cf_rows)

    effective_tax_rate = 0.30

    # PL / BS 計算
    for y in years_list:
        label = f"Year {y}"
        y_df = ledger_df[ledger_df["year"] == y] if "year" in ledger_df.columns else ledger_df
        all_until_y = (
            ledger_df[ledger_df["year"] <= y] if "year" in ledger_df.columns else ledger_df
        )

        # PL
        pl_df.loc["売上高", label] = y_df[y_df["cr_account"] == "売上高"]["amount"].sum()
        pl_df.loc["建物減価償却費", label] = y_df[y_df["dr_account"] == "建物減価償却費"]["amount"].sum()
        pl_df.loc["追加設備減価償却費", label] = y_df[y_df["dr_account"] == "追加設備減価償却費"]["amount"].sum()
        pl_df.loc["租税公課（固定資産税)", label] = y_df[y_df["dr_account"] == "租税公課（固定資産税)"]["amount"].sum()
        pl_df.loc["販売費一般管理費", label] = y_df[y_df["dr_account"] == "販売費一般管理費"]["amount"].sum()
        pl_df.loc["初期長借利息", label] = y_df[y_df["dr_account"] == "初期長借利息"]["amount"].sum()

        pl_df.loc["売上総利益", label] = pl_df.loc["売上高", label]
        pl_df.loc["営業利益", label] = (
            pl_df.loc["売上総利益", label]
            - pl_df.loc["建物減価償却費", label]
            - pl_df.loc["追加設備減価償却費", label]
            - pl_df.loc["販売費一般管理費", label]
            - pl_df.loc["租税公課（固定資産税)", label]
        )

        pl_df.loc["経常利益", label] = (
            pl_df.loc["営業利益", label]
            - pl_df.loc["初期長借利息", label]
        )

        pre_tax_profit = pl_df.loc["経常利益", label]
        tax_amount = max(0, pre_tax_profit * effective_tax_rate)

        pl_df.loc["税引前当期利益", label] = pre_tax_profit
        pl_df.loc["所得税", label] = tax_amount
        pl_df.loc["当期利益", label] = pre_tax_profit - tax_amount

        # BS（簡易）
        dr_cash = all_until_y[all_until_y["dr_account"] == "預金"]["amount"].sum()
        cr_cash = all_until_y[all_until_y["cr_account"] == "預金"]["amount"].sum()
        bs_df.loc["預金", label] = dr_cash - cr_cash
        bs_df.loc["未払所得税", label] = pl_df.loc["所得税", label]

    return {
        "pl": pl_df,
        "bs": bs_df,
        "cf": cf_df,
        "is_balanced": is_balanced,
        "debit_total": debit_total,
        "credit_total": credit_total,
        "balance_diff": balance_diff,
    }

# ----------------------------------------------------------------------
# 3. V12完全互換サイドバー（holding_years internal）
# ----------------------------------------------------------------------
def setup_sidebar() -> SimulationParams:
    CURRENCY = "%.0f"
    st.sidebar.markdown("## 🛠 ユーザー入力欄")

    # 1. 物件情報
    st.sidebar.header("🏠 1. 物件情報")
    start_date = st.sidebar.date_input(
        "シミュレーション開始日",
        value=datetime.date(2025, 1, 1),
        key="sim_start_date",
    )
    price_bld = st.sidebar.number_input(
        "建物価格（税込）",
        0.0,
        value=50_000_000.0,
        step=100_000.0,
        format=CURRENCY,
    )
    price_land = st.sidebar.number_input(
        "土地価格",
        0.0,
        value=30_000_000.0,
        step=100_000.0,
        format=CURRENCY,
    )
    brokerage_fee = st.sidebar.number_input(
        "仲介手数料（税込）",
        0.0,
        value=3_300_000.0,
        step=10_000.0,
        format=CURRENCY,
    )

    # 2. 資金調達
    st.sidebar.header("💰 2. 資金調達")
    loan_amount = st.sidebar.number_input(
        "初期借入金額",
        0.0,
        value=70_000_000.0,
        step=100_000.0,
        format=CURRENCY,
    )
    loan_years = st.sidebar.number_input(
        "返済期間（年）",
        1.0,
        50.0,
        value=30.0,
        format=CURRENCY,
    )
    loan_rate = (
        st.sidebar.number_input(
            "借入金利（年率 %）",
            0.0,
            50.0,
            value=2.5,
            step=0.01,
        )
        / 100
    )

    initial_loan = (
        LoanParams(amount=loan_amount, interest_rate=loan_rate, years=int(loan_years))
        if loan_amount > 0
        else None
    )

    total_investment = price_bld + price_land + brokerage_fee
    equity = max(total_investment - loan_amount, 0.0)
    st.sidebar.metric("元入金（自動計算）", f"{equity:,.0f}")

    # 3. 収益・費用
    st.sidebar.header("🏢 3. 収益・費用")
    annual_rent = st.sidebar.number_input(
        "年間家賃収入（税込）",
        0.0,
        value=3_600_000.0,
        step=10_000.0,
        format=CURRENCY,
    )
    mgmt_fee = st.sidebar.number_input(
        "年間管理費（税込）",
        0.0,
        value=1_200_000.0,
        step=10_000.0,
        format=CURRENCY,
    )
    repair_cost = st.sidebar.number_input(
        "年間修繕費（税込）",
        0.0,
        value=300_000.0,
        step=10_000.0,
        format=CURRENCY,
    )
    insurance = st.sidebar.number_input(
        "年間保険料（非課税）",
        0.0,
        value=100_000.0,
        step=10_000.0,
        format=CURRENCY,
    )
    fa_tax_land = st.sidebar.number_input(
        "固定資産税（土地）",
        0.0,
        value=150_000.0,
        step=10_000.0,
        format=CURRENCY,
    )
    fa_tax_bld = st.sidebar.number_input(
        "固定資産税（建物）",
        0.0,
        value=150_000.0,
        step=10_000.0,
        format=CURRENCY,
    )

    # 4. 税率
    st.sidebar.header("📊 4. 税率")
    vat_rate = (
        st.sidebar.number_input("消費税率（%）", 0.0, 50.0, value=10.0) / 100
    )
    overdraft_rate = (
        st.sidebar.number_input("当座借越金利（%）", 0.0, 50.0, value=5.0) / 100
    )

    # 5. 出口設定
    st.sidebar.header("📉 5. 出口設定")
    exit_year = st.sidebar.number_input(
        "売却予定年（シミュレーション年数）",
        min_value=1.0,
        max_value=50.0,
        value=5.0,
        step=1.0,
        format=CURRENCY,
    )
    holding_years_internal = int(exit_year)

    selling_price = st.sidebar.number_input(
        "売却価格",
        0.0,
        value=0.0,
        step=100_000.0,
        format=CURRENCY,
    )
    selling_cost = st.sidebar.number_input(
        "売却費用",
        0.0,
        value=0.0,
        step=100_000.0,
        format=CURRENCY,
    )
    income_tax_rate = (
        st.sidebar.number_input("売却益税率（%）", 1.0, 60.0, value=30.0) / 100
    )

    exit_params = ExitParams(
        exit_year=holding_years_internal,
        selling_price=selling_price,
        selling_cost=selling_cost,
        income_tax_rate=income_tax_rate,
    )

    # 6. 追加投資
    st.sidebar.header("➕ 6. 追加投資")
    additional_investments: List[AdditionalInvestmentParams] = []

    for i in range(1, 6):
        with st.sidebar.expander(f"第{i}回 追加投資"):
            amt = st.sidebar.number_input(
                "投資額",
                key=f"inv_amt_{i}",
                min_value=0.0,
                step=100_000.0,
                format=CURRENCY,
            )
            if amt > 0:
                year = st.sidebar.number_input(
                    "投資年",
                    min_value=2.0,
                    max_value=exit_year,
                    value=2.0,
                    step=1.0,
                    format=CURRENCY,
                )
                dep = st.sidebar.number_input(
                    "償却年数",
                    min_value=1.0,
                    max_value=50.0,
                    value=15.0,
                    step=1.0,
                    format=CURRENCY,
                )
                additional_investments.append(
                    AdditionalInvestmentParams(
                        invest_year=int(year),
                        invest_amount=amt,
                        depreciation_years=int(dep),
                        loan_amount=0.0,
                        loan_years=0,
                        loan_interest_rate=0.0,
                    )
                )

    params = SimulationParams(
        property_price_building=price_bld,
        property_price_land=price_land,
        brokerage_fee_amount_incl=brokerage_fee,
        building_useful_life=47,
        building_age=5,
        holding_years=holding_years_internal,
        initial_loan=initial_loan,
        initial_equity=equity,
        rent_setting_mode="AMOUNT",
        target_cap_rate=0.0,
        annual_rent_income_incl=annual_rent,
        annual_management_fee_initial=mgmt_fee,
        repair_cost_annual=repair_cost,
        insurance_cost_annual=insurance,
        fixed_asset_tax_land=fa_tax_land,
        fixed_asset_tax_building=fa_tax_bld,
        other_management_fee_annual=0.0,
        management_fee_rate=0.0,
        consumption_tax_rate=vat_rate,
        non_taxable_proportion=0.0,
        overdraft_interest_rate=overdraft_rate,
        cf_discount_rate=0.0,
        exit_params=exit_params,
        additional_investments=additional_investments,
        start_date=start_date,
    )

    return params

# ----------------------------------------------------------------------
# 4. 経済探偵レポート
# ----------------------------------------------------------------------
def economic_detective_report(fs_data: dict, params: SimulationParams, ledger_df: pd.DataFrame):
    st.subheader("🕵️‍♂️ 経済探偵の分析レポート")

    st.markdown(
        """
        <style>
        .report-card {
            background-color: #f8f9fa;
            border-left: 5px solid #2c3e50;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .report-label { font-size: 0.85rem; color: #666; font-weight: bold; }
        .report-value { font-size: 1.25rem; color: #2c3e50; font-weight: 800; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    pl = fs_data["pl"]
    bs = fs_data["bs"]

    total_rent = pl.loc["売上高"].sum() if "売上高" in pl.index else 0
    total_mgmt = pl.loc["販売費一般管理費"].sum() if "販売費一般管理費" in pl.index else 0
    mgmt_ratio = total_mgmt / total_rent if total_rent != 0 else 0

    total_tax = pl.loc["所得税"].sum() if "所得税" in pl.index else 0
    final_cash = bs.loc["預金"].iloc[-1] if "預金" in bs.index else 0

    ledger_df = ledger_df.copy()
    ledger_df["signed_amount"] = np.where(
        ledger_df["dr_cr"] == "debit",
        -ledger_df["amount"],
        ledger_df["amount"],
    )

    ledger_df["is_operating"] = ledger_df["account"].isin(
        ["売上高", "販売費一般管理費", "所得税"]
    )

    # -------------------------------
    # year / month カラム生成（なければ作る）
    # -------------------------------
    if "year" not in ledger_df.columns or "month" not in ledger_df.columns:
        date_col = None
        for cand in ["date", "booking_date", "txn_date"]:
            if cand in ledger_df.columns:
                date_col = cand
                break

        if date_col is not None:
            ledger_df[date_col] = pd.to_datetime(ledger_df[date_col])
            ledger_df["year"] = ledger_df[date_col].dt.year
            ledger_df["month"] = ledger_df[date_col].dt.month
        else:
            # 日付情報が全く無い場合: ダミーの year/month = 1 を付与
            ledger_df["year"] = 1
            ledger_df["month"] = 1

    # 営業CF（年×月）
    cf_operating = (
        ledger_df[ledger_df["is_operating"]]
        .groupby(["year", "month"], as_index=False)["signed_amount"]
        .sum()
        .sort_values(["year", "month"])
    )

    cf_operating["cum_cf"] = cf_operating["signed_amount"].cumsum()

    positive_cf_row = cf_operating[cf_operating["cum_cf"] > 0].head(1)
    positive_cf_timing = (
        f"{int(positive_cf_row.iloc[0]['year'])}年{int(positive_cf_row.iloc[0]['month'])}月"
        if not positive_cf_row.empty
        else "未達"
    )

    initial_investment = params.initial_equity
    recovery_row = cf_operating[cf_operating["cum_cf"] >= initial_investment].head(1)
    recovery_month = (
        f"{int(recovery_row.iloc[0]['year'])}年{int(recovery_row.iloc[0]['month'])}月"
        if not recovery_row.empty
        else "未回収"
    )

    total_profit = final_cash - params.initial_equity
    roi = total_profit / params.initial_equity if params.initial_equity != 0 else 0
    annual_roi = roi / params.holding_years if params.holding_years > 0 else 0

    discount_rate = params.cf_discount_rate or 0.03
    discounted_cf = [
        cf / ((1 + discount_rate) ** (i + 1))
        for i, cf in enumerate(cf_operating["signed_amount"])
    ]
    npv = sum(discounted_cf) - params.initial_equity

    operating_cf_total = cf_operating["signed_amount"].sum()

    def metric(label, value):
        return f"""
        <div class="report-card">
            <div class="report-label">{label}</div>
            <div class="report-value">{value}</div>
        </div>
        """

    st.markdown(metric("受け取った家賃収入の総額", f"{int(total_rent):,} 円"), unsafe_allow_html=True)
    st.markdown(metric("支払った管理費の総額", f"{int(total_mgmt):,} 円"), unsafe_allow_html=True)
    st.markdown(metric("管理費 ÷ 収入", f"{mgmt_ratio:.1%}"), unsafe_allow_html=True)
    st.markdown(metric("支払った税金の総額", f"{int(total_tax):,} 円"), unsafe_allow_html=True)
    st.markdown(metric("資金収支がプラスになる時期", positive_cf_timing), unsafe_allow_html=True)
    st.markdown(metric("投資回収完了月", recovery_month), unsafe_allow_html=True)
    st.markdown(metric("売却時に手元に残った金額", f"{int(final_cash):,} 円"), unsafe_allow_html=True)
    st.markdown(metric("全体の投資利回り", f"{roi:.1%}"), unsafe_allow_html=True)
    st.markdown(metric("上記年率", f"{annual_roi:.1%}"), unsafe_allow_html=True)
    st.markdown(metric("DCF法による現在価値", f"{int(npv):,} 円"), unsafe_allow_html=True)
    st.markdown(
        metric(
            "借入返済期間中の営業収支合計",
            f"{int(operating_cf_total):,} 円",
        ),
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# 5. メイン
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 5. メイン
# ----------------------------------------------------------------------

def main():
    st.set_page_config(layout="wide", page_title="BKW Invest Sim (Amelia V20統合版)")

    # ============================================================
    # 共通CSS（カード・見出し・ボタン・簿記検証）
    # ============================================================
    st.markdown(
        """
        <style>
        .bkw-card {
            background-color:#f8f9fa;
            border-left:6px solid #2c3e50;
            padding:18px 22px;
            margin-bottom:16px;
            border-radius:10px;
            display:flex;
            flex-direction:column;
        }

        .bkw-label {
            font-size:1.8rem;
            font-weight:800;
            color:#333;
            margin-bottom:8px;
        }

        .bkw-value {
            font-size:1.8rem;
            font-weight:800;
            color:#111;
            text-align:right;
            font-variant-numeric: tabular-nums;
        }

        .bkw-section-title {
            font-size:1.8rem;
            font-weight:900;
            margin-top:36px;
            margin-bottom:24px;
        }

        /* 実行ボタン */
        div.stButton > button {
            font-size:1.8rem !important;
            font-weight:900 !important;
            padding:0.9em 1.2em !important;
        }

        /* 簿記検証（特大） */
        .bkw-balance-check {
            font-size:2.4rem;
            font-weight:900;
            padding:18px 22px;
            border-radius:10px;
            margin-top:20px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # タイトル
    # ============================================================
    st.title("💰 BKW 不動産投資シミュレーション (V20: UI+ロジック完全統合版)")

    # ============================================================
    # サイドバー入力 → params
    # ============================================================
    params = setup_sidebar()

    # ============================================================
    # 前提条件（カード・左右2列）
    # ============================================================
    st.markdown(
        '<div class="bkw-section-title">📋 シミュレーション前提条件（入力値）</div>',
        unsafe_allow_html=True,
    )

    def summary_card(label, value):
        return f"""
        <div class="bkw-card">
            <div class="bkw-label">{label}</div>
            <div class="bkw-value">{value}</div>
        </div>
        """

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(summary_card("建物価格", f"{params.property_price_building:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("土地価格", f"{params.property_price_land:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("仲介手数料", f"{params.brokerage_fee_amount_incl:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("元入金", f"{params.initial_equity:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("年間家賃収入", f"{params.annual_rent_income_incl:,.0f}"), unsafe_allow_html=True)

    with col_r:
        st.markdown(summary_card("年間管理費", f"{params.annual_management_fee_initial:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("固定資産税（土地）", f"{params.fixed_asset_tax_land:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("固定資産税（建物）", f"{params.fixed_asset_tax_building:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("保有年数", f"{params.holding_years}"), unsafe_allow_html=True)
        st.markdown(summary_card("追加投資件数", f"{len(params.additional_investments)}"), unsafe_allow_html=True)

    # ============================================================
    # 実行ボタン
    # ============================================================
    run_clicked = st.button("▶︎ シミュレーション実行", type="primary", use_container_width=True)

    # ============================================================
    # 実行後
    # ============================================================
    if run_clicked:
        try:
            sim = Simulation(params, params.start_date)
            sim.run()
            ledger_df = sim.ledger.get_df()

            fs_data = create_financial_statements(ledger_df, params.holding_years)
            display_fs = create_display_dataframes(fs_data)

            # ---- 簿記検証 ----
            diff = fs_data["balance_diff"]
            if fs_data["is_balanced"]:
                st.markdown(
                    f"""
                    <div class="bkw-balance-check" style="background:#e6f4ea;color:#1e4620;">
                        ✅ 簿記検証：正常（借方 {int(fs_data['debit_total']):,} /
                        貸方 {int(fs_data['credit_total']):,} / 差額 {diff:,.0f}）
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="bkw-balance-check" style="background:#fdecea;color:#611a15;">
                        ❌ 簿記検証：不一致（借方 {int(fs_data['debit_total']):,} /
                        貸方 {int(fs_data['credit_total']):,} / 差額 {diff:,.0f}）
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # ====================================================
            # 経済探偵レポート（カード・左右2列）
            # ====================================================
            st.markdown(
                '<div class="bkw-section-title">🕵️‍♂️ 経済探偵の分析レポート</div>',
                unsafe_allow_html=True,
            )

            # ★ ここが最大の修正点：metrics を main 側で定義
            metrics = [
                ("受け取った家賃収入の総額", f"{fs_data.get('total_rent_income', 0):,.0f}"),
                ("支払った管理費の総額", f"{fs_data.get('total_management_fee', 0):,.0f}"),
                ("管理費 ÷ 収入", f"{fs_data.get('management_ratio', 0):.1%}"),
                ("支払った税金の総額", f"{fs_data.get('total_tax', 0):,.0f}"),
                ("資金収支がプラスになる時期", fs_data.get("cashflow_positive_year", "未達")),
                ("投資回収完了月", fs_data.get("payback_period", "未回収")),
                ("売却時に手元に残った金額", f"{fs_data.get('final_cash', 0):,.0f}"),
                ("全体の投資利回り", f"{fs_data.get('roi', 0):.1%}"),
            ]

            mid = (len(metrics) + 1) // 2
            left_metrics = metrics[:mid]
            right_metrics = metrics[mid:]

            col_l, col_r = st.columns(2)

            with col_l:
                for label, value in left_metrics:
                    st.markdown(summary_card(label, value), unsafe_allow_html=True)

            with col_r:
                for label, value in right_metrics:
                    st.markdown(summary_card(label, value), unsafe_allow_html=True)

            # ====================================================
            # 財務三表
            # ====================================================
            tabs = st.tabs(["📊 損益計算書", "🏦 貸借対照表", "💸 資金収支", "📒 全仕訳"])

            with tabs[0]:
                st.dataframe(display_fs["pl"], use_container_width=True)
            with tabs[1]:
                st.dataframe(display_fs["bs"], use_container_width=True)
            with tabs[2]:
                st.dataframe(display_fs["cf"], use_container_width=True)
            with tabs[3]:
                st.dataframe(ledger_df, use_container_width=True)

        except Exception as e:
            st.error(f"シミュレーションエラー: {str(e)}")
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()

# ============== bkw_sim_amelia1/ui/app.py ==============　end