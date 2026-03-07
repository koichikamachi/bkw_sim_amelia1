# ==============================
#  bkw_sim_amelia1/ui/app.py
#  訂正済み版（仕様書v4訂正済に準拠）
# ==============================

import os
import sys

# ------------------------------------------------------------
# ① プロジェクトのルートを Python path に追加（必ず最初に）
# ------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))       # /bkw_sim_amelia1/ui
project_root = os.path.abspath(os.path.join(current_dir, "..")) # /bkw_sim_amelia1
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ------------------------------------------------------------
# ② 通常 import
# ------------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import traceback
from typing import List
from io import BytesIO

# ------------------------------------------------------------
# ③ core.* import（パス追加後に行う）
# ------------------------------------------------------------
from config.params import (
    SimulationParams,
    LoanParams,
    ExitParams,
    AdditionalInvestmentParams,
)
from core.simulation.simulation import Simulation
from core.finance.fs_builder import FinancialStatementBuilder


# ----------------------------------------------------------------------
# CSS 設定
# ----------------------------------------------------------------------
def inject_global_css():
    st.markdown(
        """
        <style>
        .bkw-card {
            background-color: #f4f5f7;
            border-left: 4px solid #2c3e50;
            padding: 12px 16px;
            margin-bottom: 10px;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
        }
        .bkw-label {
            font-size: 1.05rem;
            font-weight: 700;
            color: #444;
            margin-bottom: 2px;
            line-height: 1.2;
        }
        .bkw-value {
            font-size: 1.15rem;
            font-weight: 800;
            color: #111;
            text-align: right;
            font-variant-numeric: tabular-nums;
            line-height: 1.25;
        }
        .bkw-section-title {
            font-size: 1.25rem;
            font-weight: 800;
            margin-top: 26px;
            margin-bottom: 14px;
            color: #e5e7eb;
        }
        div.stButton > button {
            font-size: 1.1rem !important;
            font-weight: 800 !important;
            padding: 0.6em 1.1em !important;
        }
        .bkw-balance-check {
            font-size: 1.3rem;
            font-weight: 800;
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 16px;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# 表示用 DataFrame 生成
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
# FS レンダリング関数
# ----------------------------------------------------------------------
def render_pl(display_fs):
    st.markdown("### 📊 損益計算書（PL）")
    st.dataframe(display_fs["pl"], use_container_width=True)


def render_bs(display_fs):
    st.markdown("### 🏦 貸借対照表（BS）")
    st.dataframe(display_fs["bs"], use_container_width=True)


def render_cf(display_fs):
    st.markdown("### 💸 資金収支計算書（CF）")
    st.dataframe(display_fs["cf"], use_container_width=True)


# ----------------------------------------------------------------------
# 追加投資サイドバー（内部処理用）
# ※ フィールド名は仕様書統一表に従い year / amount / life を使用
# ----------------------------------------------------------------------
def _setup_additional_investments_internal(
    num_investments: int,
    exit_year: int,
) -> List[AdditionalInvestmentParams]:
    investments: List[AdditionalInvestmentParams] = []
    if num_investments == 0:
        return investments

    st.sidebar.markdown("### 📌 追加投資の詳細入力")

    for i in range(1, num_investments + 1):
        with st.sidebar.expander(f"第{i}回 追加投資", expanded=True):

            inv_year = st.number_input(
                "投資年",
                min_value=1,
                max_value=exit_year,
                value=1,
                step=1,
                key=f"add_inv_year_{i}",
            )
            inv_amount = st.number_input(
                "投資金額（税込）",
                min_value=0.0,
                step=100_000.0,
                format="%.0f",
                key=f"add_inv_amount_{i}",
            )
            inv_life = st.number_input(
                "耐用年数",
                min_value=1,
                max_value=50,
                value=15,
                step=1,
                key=f"add_inv_life_{i}",
            )
            inv_loan = st.number_input(
                "付随借入金額",
                min_value=0.0,
                step=100_000.0,
                format="%.0f",
                key=f"add_inv_loan_{i}",
            )
            inv_loan_years = st.number_input(
                "借入期間（年）",
                min_value=0,
                max_value=50,
                value=0,
                step=1,
                key=f"add_inv_loan_years_{i}",
            )
            inv_loan_rate = (
                st.number_input(
                    "借入利率（%）",
                    min_value=0.0,
                    max_value=50.0,
                    value=0.0,
                    step=0.01,
                    key=f"add_inv_loan_rate_{i}",
                )
                / 100
            )

            if inv_amount > 0:
                investments.append(
                    AdditionalInvestmentParams(
                        year=int(inv_year),          # 正式フィールド名
                        amount=float(inv_amount),    # 正式フィールド名
                        life=int(inv_life),          # 正式フィールド名
                        loan_amount=float(inv_loan),
                        loan_years=int(inv_loan_years),
                        loan_interest_rate=float(inv_loan_rate),
                    )
                )

    return investments


def setup_additional_investments_sidebar(
    holding_years_internal: int,
) -> List[AdditionalInvestmentParams]:
    st.sidebar.header("➕ 6. 追加投資")
    num = st.sidebar.number_input(
        "追加投資回数",
        min_value=0,
        max_value=5,
        value=0,
        step=1,
    )
    return _setup_additional_investments_internal(
        num_investments=num,
        exit_year=holding_years_internal,
    )


# ----------------------------------------------------------------------
# サイドバー全体
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
        "建物価格（税込）", 0.0, value=50_000_000.0, step=100_000.0, format=CURRENCY
    )
    price_land = st.sidebar.number_input(
        "土地価格（非課税）", 0.0, value=30_000_000.0, step=100_000.0, format=CURRENCY
    )
    brokerage_fee = st.sidebar.number_input(
        "仲介手数料（税込）", 0.0, value=3_300_000.0, step=10_000.0, format=CURRENCY
    )
    building_useful_life = st.sidebar.number_input(
        "建物耐用年数（年）※税法上の耐用年数をユーザーが計算して入力",
        min_value=1, max_value=60, value=47, step=1,
        key="building_useful_life",
    )
    building_age = st.sidebar.number_input(
        "建物築年数（年）※演算には使用しません",
        min_value=0, max_value=60, value=5, step=1,
        key="building_age",
    )

    # 2. 資金調達
    st.sidebar.header("💰 2. 資金調達")
    loan_amount = st.sidebar.number_input(
        "初期借入金額", 0.0, value=70_000_000.0, step=100_000.0, format=CURRENCY
    )
    loan_years = st.sidebar.number_input(
        "返済期間（年）", 1.0, 50.0, value=30.0, format=CURRENCY
    )
    loan_rate = (
        st.sidebar.number_input("借入金利（年率 %）", 0.0, 50.0, value=2.5, step=0.01)
        / 100
    )
    repayment_method = st.sidebar.selectbox(
        "返済方式",
        options=["annuity", "equal_principal"],
        format_func=lambda x: "元利均等" if x == "annuity" else "元金均等",
        key="repayment_method",
    )

    initial_loan = (
        LoanParams(
            amount=loan_amount,
            interest_rate=loan_rate,
            years=int(loan_years),
            repayment_method=repayment_method,
        )
        if loan_amount > 0
        else None
    )

    total_investment = price_bld + price_land + brokerage_fee
    equity = float(max(total_investment - loan_amount, 0.0))
    st.sidebar.metric("元入金（自動計算）", f"{equity:,.0f}")

    # 3. 収益・費用
    st.sidebar.header("🏢 3. 収益・費用")
    annual_rent = st.sidebar.number_input(
        "年間家賃収入（税込）", 0.0, value=3_600_000.0, step=10_000.0, format=CURRENCY
    )
    non_taxable_proportion = st.sidebar.number_input(
        "非課税割合（住宅割合 0.0〜1.0）",
        min_value=0.0, max_value=1.0, value=0.0, step=0.05,
    )
    mgmt_fee = st.sidebar.number_input(
        "年間管理費（税込）", 0.0, value=1_200_000.0, step=10_000.0, format=CURRENCY
    )
    repair_cost = st.sidebar.number_input(
        "年間修繕費（税込）", 0.0, value=300_000.0, step=10_000.0, format=CURRENCY
    )
    insurance = st.sidebar.number_input(
        "年間保険料（非課税）", 0.0, value=100_000.0, step=10_000.0, format=CURRENCY
    )
    fa_tax_land = st.sidebar.number_input(
        "固定資産税（土地）", 0.0, value=150_000.0, step=10_000.0, format=CURRENCY
    )
    fa_tax_bld = st.sidebar.number_input(
        "固定資産税（建物）", 0.0, value=150_000.0, step=10_000.0, format=CURRENCY
    )
    other_mgmt_fee = st.sidebar.number_input(
        "その他販管費（税込・年額）", 0.0, value=0.0, step=10_000.0, format=CURRENCY
    )

    # 4. 税率設定
    st.sidebar.header("📊 4. 税率設定")
    vat_rate = (
        st.sidebar.number_input("消費税率（%）", 0.0, 50.0, value=10.0) / 100
    )
    entity_type = st.sidebar.selectbox(
        "課税主体",
        options=["individual", "corporate"],
        format_func=lambda x: "個人" if x == "individual" else "法人",
        key="entity_type",
    )
    if entity_type == "individual":
        tax_rate = (
            st.sidebar.number_input(
                "所得税率（%）", 0.0, 100.0, value=20.0, step=0.1
            )
            / 100
        )
    else:
        tax_rate = (
            st.sidebar.number_input(
                "法人税率（%）", 0.0, 100.0, value=30.0, step=0.1
            )
            / 100
        )
    overdraft_rate = (
        st.sidebar.number_input("当座借越金利（%）", 0.0, 50.0, value=5.0) / 100
    )

    # 5. 出口設定
    st.sidebar.header("📉 5. 出口設定")
    exit_year = st.sidebar.number_input(
        "売却予定年（保有年数）",
        min_value=1, max_value=50, value=5, step=1,
    )
    holding_years_internal = int(exit_year)

    with st.sidebar:
        st.markdown("### 🏁 物件売却（出口）")
        col1, col2 = st.columns(2)
        with col1:
            land_exit_price = st.number_input(
                "土地売却額（非課税）",
                min_value=0.0, step=100_000.0, format="%.0f",
                key="land_exit_price",
            )
        with col2:
            building_exit_price = st.number_input(
                "建物売却額（税込）",
                min_value=0.0, step=100_000.0, format="%.0f",
                key="building_exit_price",
            )
        exit_cost = st.number_input(
            "売却費用（税込）",
            min_value=0.0, step=10_000.0, format="%.0f",
            key="exit_cost",
        )

    exit_params = ExitParams(
        exit_year=holding_years_internal,
        land_exit_price=float(land_exit_price),
        building_exit_price=float(building_exit_price),
        exit_cost=float(exit_cost),
    )

    # 6. 追加投資
    additional_investments = setup_additional_investments_sidebar(holding_years_internal)

    # SimulationParams 生成
    params = SimulationParams(
        property_price_building=float(price_bld),
        property_price_land=float(price_land),
        brokerage_fee_amount_incl=float(brokerage_fee),
        building_useful_life=int(building_useful_life),
        building_age=int(building_age),
        holding_years=holding_years_internal,
        initial_loan=initial_loan,
        initial_equity=equity,
        rent_setting_mode="AMOUNT",
        target_cap_rate=0.0,
        annual_rent_income_incl=float(annual_rent),
        annual_management_fee_initial=float(mgmt_fee),
        repair_cost_annual=float(repair_cost),
        insurance_cost_annual=float(insurance),
        fixed_asset_tax_land=float(fa_tax_land),
        fixed_asset_tax_building=float(fa_tax_bld),
        other_management_fee_annual=float(other_mgmt_fee),
        management_fee_rate=0.0,
        consumption_tax_rate=float(vat_rate),
        non_taxable_proportion=float(non_taxable_proportion),
        overdraft_interest_rate=float(overdraft_rate),
        cf_discount_rate=0.0,
        exit_params=exit_params,
        additional_investments=additional_investments,
        start_date=start_date,
        entity_type=entity_type,
        income_tax_rate=tax_rate if entity_type == "individual" else 0.0,
        corporate_tax_rate=tax_rate if entity_type == "corporate" else 0.0,
    )
    return params


# ----------------------------------------------------------------------
# 経済探偵レポート
# ----------------------------------------------------------------------
def economic_detective_report(
    fs_data: dict, params: SimulationParams, ledger_df: pd.DataFrame
):
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

    total_rent   = pl.loc["売上高"].sum()            if "売上高"           in pl.index else 0
    total_mgmt   = pl.loc["販売費一般管理費"].sum()  if "販売費一般管理費" in pl.index else 0
    mgmt_ratio   = total_mgmt / total_rent           if total_rent != 0    else 0
    # 仕様書統一名：所得税（法人税）
    total_tax    = pl.loc["所得税（法人税）"].sum()  if "所得税（法人税）" in pl.index else 0
    final_cash   = bs.loc["預金"].iloc[-1]           if "預金"             in bs.index else 0

    ledger_df = ledger_df.copy()
    ledger_df["signed_amount"] = np.where(
        ledger_df["dr_cr"] == "debit", -ledger_df["amount"], ledger_df["amount"]
    )
    ledger_df["is_operating"] = ledger_df["account"].isin(
        ["売上高", "販売費一般管理費", "所得税（法人税）"]
    )

    # year / month カラム生成
    if "year" not in ledger_df.columns or "month" not in ledger_df.columns:
        date_col = next(
            (c for c in ["date", "booking_date", "txn_date"] if c in ledger_df.columns),
            None,
        )
        if date_col:
            ledger_df[date_col] = pd.to_datetime(ledger_df[date_col])
            ledger_df["year"]  = ledger_df[date_col].dt.year
            ledger_df["month"] = ledger_df[date_col].dt.month
        else:
            ledger_df["year"]  = 1
            ledger_df["month"] = 1

    cf_operating = (
        ledger_df[ledger_df["is_operating"]]
        .groupby(["year", "month"], as_index=False)["signed_amount"]
        .sum()
        .sort_values(["year", "month"])
    )
    cf_operating["cum_cf"] = cf_operating["signed_amount"].cumsum()

    pos_row = cf_operating[cf_operating["cum_cf"] > 0].head(1)
    positive_cf_timing = (
        f"{int(pos_row.iloc[0]['year'])}年{int(pos_row.iloc[0]['month'])}月"
        if not pos_row.empty else "未達"
    )

    rec_row = cf_operating[cf_operating["cum_cf"] >= params.initial_equity].head(1)
    recovery_month = (
        f"{int(rec_row.iloc[0]['year'])}年{int(rec_row.iloc[0]['month'])}月"
        if not rec_row.empty else "未回収"
    )

    total_profit = final_cash - params.initial_equity
    roi          = total_profit / params.initial_equity if params.initial_equity != 0 else 0
    annual_roi   = roi / params.holding_years           if params.holding_years > 0   else 0

    discount_rate = params.cf_discount_rate or 0.03
    npv = sum(
        cf / ((1 + discount_rate) ** (i + 1))
        for i, cf in enumerate(cf_operating["signed_amount"])
    ) - params.initial_equity

    operating_cf_total = cf_operating["signed_amount"].sum()

    col_l, col_r = st.columns(2)
    cards = [
        ("受け取った家賃収入の総額",         f"{int(total_rent):,} 円"),
        ("支払った管理費の総額",             f"{int(total_mgmt):,} 円"),
        ("管理費 ÷ 収入",                   f"{mgmt_ratio:.1%}"),
        ("支払った税金の総額",               f"{int(total_tax):,} 円"),
        ("資金収支がプラスになる時期",       positive_cf_timing),
        ("投資回収完了月",                   recovery_month),
        ("売却時に手元に残った金額",         f"{int(final_cash):,} 円"),
        ("全体の投資利回り",                 f"{roi:.1%}"),
        ("上記年率",                         f"{annual_roi:.1%}"),
        ("DCF法による現在価値",             f"{int(npv):,} 円"),
        ("借入返済期間中の営業収支合計",     f"{int(operating_cf_total):,} 円"),
    ]

    def card_html(label, value):
        return (
            f'<div class="bkw-card">'
            f'<div class="bkw-label">{label}</div>'
            f'<div class="bkw-value">{value}</div>'
            f"</div>"
        )

    for i, (label, value) in enumerate(cards):
        target = col_l if i % 2 == 0 else col_r
        target.markdown(card_html(label, value), unsafe_allow_html=True)


# ----------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------
def main():
    st.set_page_config(
        layout="wide",
        page_title="BKW Invest Sim (Amelia v4訂正済)",
    )
    inject_global_css()
    st.title("💰 BKW 不動産投資シミュレーション")
    st.caption("仕様書 v4訂正済準拠版")

    # ---- サイドバー入力 → params ----
    params = setup_sidebar()

    # ============================================================
    # システム健全性レポート（仕様書 12.8節：実行前は非表示）
    # ============================================================

    # ---- 前提条件サマリー ----
    st.markdown(
        '<div class="bkw-section-title">📋 シミュレーション前提条件（入力値確認）</div>',
        unsafe_allow_html=True,
    )

    def summary_card(label, value):
        return (
            f'<div class="bkw-card">'
            f'<div class="bkw-label">{label}</div>'
            f'<div class="bkw-value">{value}</div>'
            f"</div>"
        )

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(summary_card("建物価格（税込）",       f"{params.property_price_building:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("土地価格（非課税）",     f"{params.property_price_land:,.0f}"),     unsafe_allow_html=True)
        st.markdown(summary_card("仲介手数料（税込）",     f"{params.brokerage_fee_amount_incl:,.0f}"),unsafe_allow_html=True)
        st.markdown(summary_card("元入金",                 f"{params.initial_equity:,.0f}"),          unsafe_allow_html=True)
        st.markdown(summary_card("年間家賃収入（税込）",   f"{params.annual_rent_income_incl:,.0f}"),  unsafe_allow_html=True)
        st.markdown(summary_card("非課税割合（住宅割合）", f"{params.non_taxable_proportion:.0%}"),    unsafe_allow_html=True)
    with col_r:
        st.markdown(summary_card("年間管理費",             f"{params.annual_management_fee_initial:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("固定資産税（土地）",     f"{params.fixed_asset_tax_land:,.0f}"),     unsafe_allow_html=True)
        st.markdown(summary_card("固定資産税（建物）",     f"{params.fixed_asset_tax_building:,.0f}"), unsafe_allow_html=True)
        st.markdown(summary_card("保有年数",               f"{params.holding_years} 年"),              unsafe_allow_html=True)
        st.markdown(summary_card("課税主体",               "個人" if params.entity_type == "individual" else "法人"), unsafe_allow_html=True)
        st.markdown(summary_card("追加投資件数",           f"{len(params.additional_investments)} 件"),unsafe_allow_html=True)

    # ---- 追加投資詳細 ----
    if params.additional_investments:
        st.markdown(
            '<div class="bkw-section-title">➕ 追加投資の詳細（入力値確認）</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(5)
        for idx, inv in enumerate(params.additional_investments):
            with cols[idx % 5]:
                st.markdown(
                    f"""
                    <div class="bkw-card" style="min-height:210px;padding:10px;margin-bottom:12px;">
                        <div class="bkw-label">第{idx+1}回 追加投資</div>
                        <div class="bkw-value" style="font-size:1.0rem;text-align:left;">
                            投資年：{inv.year} 年目<br>
                            投資金額：{inv.amount:,.0f} 円<br>
                            耐用年数：{inv.life} 年<br>
                            借入金額：{inv.loan_amount:,.0f} 円<br>
                            借入利率：{inv.loan_interest_rate:.2%}<br>
                            返済年数：{inv.loan_years} 年
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.info("※ 同じ年に複数の追加投資がある場合、シミュレーション内部では合算して処理されます。")

    # ---- 実行ボタン ----
    run_clicked = st.button(
        "▶︎ シミュレーション実行",
        type="primary",
        use_container_width=True,
    )

    # ---- 実行後処理 ----
    if run_clicked:
        try:
            sim = Simulation(params, params.start_date)
            sim.run()

            ledger_df = sim.ledger.get_df()
            ledger_df_sorted = ledger_df.sort_values(
                by=["date", "id"], ascending=[True, True]
            ).reset_index(drop=True)

            # FS ビルド
            fs_builder = FinancialStatementBuilder(sim.ledger)
            fs_data    = fs_builder.build()
            display_fs = create_display_dataframes(fs_data)

            # ============================================================
            # 12.8節：システム健全性レポート（最上段に表示）
            # ============================================================
            diff = fs_data.get("balance_diff", 0)
            if fs_data.get("is_balanced", False):
                st.success(f"✅ 貸借合致：システムの整合性は正常です。（差額 {diff:.0f} 円）")
            else:
                st.error(
                    f"❌ 貸借不一致があります。使用を停止し、運用側にご連絡ください。"
                    f"（差額 {diff:.0f} 円）"
                )

            # 経済探偵レポート
            economic_detective_report(fs_data, params, ledger_df_sorted)

            # セッション保存（タブ表示用）
            st.session_state["display_fs"]      = display_fs
            st.session_state["ledger_df_sorted"] = ledger_df_sorted

        except Exception as e:
            st.error(f"シミュレーションエラー: {str(e)}")
            st.code(traceback.format_exc())
            return

    # ---- 財務三表タブ（セッションにデータがあれば常に表示）----
    if "display_fs" in st.session_state:
        display_fs       = st.session_state["display_fs"]
        ledger_df_sorted = st.session_state["ledger_df_sorted"]

        tabs = st.tabs([
            "📊 損益計算書（PL）",
            "🏦 貸借対照表（BS）",
            "💸 資金収支（CF）",
            "📒 全仕訳",
        ])
        with tabs[0]: render_pl(display_fs)
        with tabs[1]: render_bs(display_fs)
        with tabs[2]: render_cf(display_fs)
        with tabs[3]: st.dataframe(ledger_df_sorted, use_container_width=True)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()