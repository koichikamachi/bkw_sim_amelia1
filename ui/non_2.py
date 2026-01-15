# ============== bkw_sim_amelia1/ui/app.py ==============

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import traceback
import sys
import os
from typing import Optional, List

# ----------------------------------------------------------------------
# パス解決
# ----------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from config.params import (
    SimulationParams,
    LoanParams,
    ExitParams,
    AdditionalInvestmentParams,
)
from core.simulation.simulation import Simulation

# ----------------------------------------------------------------------
# CSS
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
        .bkw-label { font-size: 1.05rem; font-weight: 700; color: #444; margin-bottom: 2px; }
        .bkw-value { font-size: 1.15rem; font-weight: 800; color: #111; text-align: right; }
        .bkw-section-title { font-size: 1.25rem; font-weight: 800; margin-top: 26px; margin-bottom: 14px; color: #e5e7eb; }
        div.stButton > button { font-size: 1.1rem !important; font-weight: 800 !important; padding: 0.6em 1.1em !important; }
        .bkw-balance-check { font-size: 1.3rem; font-weight: 800; padding: 12px 16px; border-radius: 8px; margin-top: 16px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def create_display_dataframes(fs_data: dict) -> dict:
    display_dfs = {}
    def format_cell(val):
        if pd.isna(val) or (isinstance(val, float) and np.isnan(val)): return ""
        if isinstance(val, (int, float, np.integer, np.floating)):
            try: return f"{int(round(float(val))):,}"
            except: return str(val)
        return str(val)
    for key in ["pl", "bs", "cf"]:
        if key in fs_data:
            df = fs_data[key].copy()
            df_display = df.reset_index() if df.index.name == "科目" else df.copy()
            num_cols = [c for c in df_display.columns if c.startswith("Year")]
            for col in num_cols: df_display[col] = df_display[col].apply(format_cell)
            if "科目" in df_display.columns: df_display = df_display.set_index("科目")
            display_dfs[key] = df_display
    return display_dfs

def _setup_additional_investments_internal(num_investments: int, exit_year: int) -> List[AdditionalInvestmentParams]:
    investments = []
    if num_investments == 0: return investments
    st.sidebar.markdown("### 📌 追加投資の詳細入力")
    for i in range(1, num_investments + 1):
        with st.sidebar.expander(f"第{i}回 追加投資", expanded=True):
            invest_year = st.number_input("投資年", 1, exit_year, 1, 1, key=f"add_inv_year_{i}")
            invest_amount = st.number_input("投資金額", 0.0, step=100000.0, format="%.0f", key=f"add_inv_amount_{i}")
            depr_years = st.number_input("耐用年数", 1, 50, 15, 1, key=f"add_inv_dep_{i}")
            if invest_amount > 0:
                investments.append(AdditionalInvestmentParams(
                    invest_year=int(invest_year), invest_amount=float(invest_amount),
                    depreciation_years=int(depr_years), loan_amount=0.0, loan_years=0, loan_interest_rate=0.0
                ))
    return investments

def setup_additional_investments_sidebar(holding_years_internal: int) -> List[AdditionalInvestmentParams]:
    st.sidebar.header("➕ 6. 追加投資")
    num_inv = st.sidebar.number_input("追加投資回数", 0, 5, 0, 1)
    additional_investments = _setup_additional_investments_internal(num_inv, holding_years_internal)
    for inv in additional_investments: inv.invest_year = int(inv.invest_year)
    return additional_investments

def setup_sidebar() -> SimulationParams:
    CURRENCY = "%.0f"
    st.sidebar.markdown("## 🛠 ユーザー入力欄")
    st.sidebar.header("🏠 1. 物件情報")
    start_date = st.sidebar.date_input("シミュレーション開始日", value=datetime.date(2025, 1, 1), key="sim_start_date")
    price_bld = st.sidebar.number_input("建物価格（税込）", 0.0, value=50000000.0, format=CURRENCY)
    price_land = st.sidebar.number_input("土地価格", 0.0, value=30000000.0, format=CURRENCY)
    brokerage = st.sidebar.number_input("仲介手数料（税込）", 0.0, value=3300000.0, format=CURRENCY)
    useful_life = st.sidebar.number_input("建物の耐用年数（年）", 1, 60, 47)
    building_age = st.sidebar.number_input("建物の築年数（年）", 0, 60, 5)

    st.sidebar.header("💰 2. 資金調達")
    loan_amt = st.sidebar.number_input("初期借入金額", 0.0, value=70000000.0, format=CURRENCY)
    loan_yrs = st.sidebar.number_input("返済期間（年）", 1, 50, 30)
    loan_rate = st.sidebar.number_input("借入金利（%）", 0.0, 50.0, 2.5, step=0.01) / 100
    initial_loan = LoanParams(amount=float(loan_amt), interest_rate=float(loan_rate), years=int(loan_yrs)) if loan_amt > 0 else None
    equity = float(max(price_bld + price_land + brokerage - loan_amt, 0.0))
    st.sidebar.metric("元入金（自動計算）", f"{equity:,.0f}")

    st.sidebar.header("🏢 3. 収益・費用")
    rent = st.sidebar.number_input("年間家賃収入（税込）", 0.0, value=3600000.0, format=CURRENCY)
    mgmt = st.sidebar.number_input("年間管理費（税込）", 0.0, value=1200000.0, format=CURRENCY)
    repair = st.sidebar.number_input("年間修繕費（税込）", 0.0, value=300000.0, format=CURRENCY)
    tax_land = st.sidebar.number_input("固定資産税（土地）", 0.0, value=150000.0, format=CURRENCY)
    tax_bld = st.sidebar.number_input("固定資産税（建物）", 0.0, value=150000.0, format=CURRENCY)

    st.sidebar.header("📊 4. 税率")
    vat = st.sidebar.number_input("消費税率（%）", 0.0, 50.0, 10.0) / 100
    non_tax_prop = st.sidebar.number_input("非課税割合（0-1.0）", 0.0, 1.0, 0.0, 0.05)

    st.sidebar.header("📉 5. 出口設定")
    exit_y = int(st.sidebar.number_input("売却予定年", 1.0, 50.0, 5.0))
    sell_p = st.sidebar.number_input("売却価格", 0.0, value=0.0, format=CURRENCY)
    exit_tax = st.sidebar.number_input("売却益税率（%）", 1, 60, 30) / 100
    exit_params = ExitParams(exit_year=exit_y, selling_price=float(sell_p), selling_cost=0.0, income_tax_rate=float(exit_tax))

    add_inv = setup_additional_investments_sidebar(exit_y)

    return SimulationParams(
        property_price_building=float(price_bld), property_price_land=float(price_land),
        brokerage_fee_amount_incl=float(brokerage), building_useful_life=int(useful_life),
        building_age=int(building_age), holding_years=int(exit_y), initial_loan=initial_loan,
        initial_equity=equity, rent_setting_mode="AMOUNT", annual_rent_income_incl=float(rent),
        annual_management_fee_initial=float(mgmt), repair_cost_annual=float(repair),
        fixed_asset_tax_land=float(tax_land), fixed_asset_tax_building=float(tax_bld),
        consumption_tax_rate=float(vat), non_taxable_proportion=float(non_tax_prop),
        exit_params=exit_params, additional_investments=add_inv, start_date=start_date
    )

def economic_detective_report(fs_data: dict, params: SimulationParams, ledger_df: pd.DataFrame):
    st.subheader("🕵️‍♂️ 経済探偵の分析レポート")
    pl, bs = fs_data["pl"], fs_data["bs"]
    total_rent = pl.loc["売上高"].sum() if "売上高" in pl.index else 0
    total_tax = pl.loc["所得税"].sum() if "所得税" in pl.index else 0
    final_cash = bs.loc["預金"].iloc[-1] if "預金" in bs.index else 0
    roi = (final_cash - params.initial_equity) / params.initial_equity if params.initial_equity != 0 else 0
    col_l, col_r = st.columns(2)
    cards = [
        ("家賃収入総額", f"{int(total_rent):,} 円"),
        ("支払った税金総額", f"{int(total_tax):,} 円"),
        ("最終手元現金", f"{int(final_cash):,} 円"),
        ("投資利回り (ROI)", f"{roi:.1%}")
    ]
    for i, (l, v) in enumerate(cards):
        html = f'<div class="bkw-card"><div class="bkw-label">{l}</div><div class="bkw-value">{v}</div></div>'
        (col_l if i % 2 == 0 else col_r).markdown(html, unsafe_allow_html=True)

def main():
    st.set_page_config(layout="wide", page_title="BKW Invest Sim V20")
    inject_global_css()
    st.title("💰 BKW 不動産投資シミュレーション")
    st.caption("Amelia V20 統合修正版 - インデント完全復旧")

    params = setup_sidebar()
    st.markdown('<div class="bkw-section-title">📋 シミュレーション前提条件</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f'<div class="bkw-card"><div class="bkw-label">建物価格</div><div class="bkw-value">{params.property_price_building:,.0f} 円</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="bkw-card"><div class="bkw-label">保有年数</div><div class="bkw-value">{params.holding_years} 年</div></div>', unsafe_allow_html=True)

    if st.button("▶︎ シミュレーション実行", type="primary", use_container_width=True):
        try:
            sim = Simulation(params, params.start_date)
            sim.run()
            ledger_df = sim.ledger.get_df()

            from core.finance.fs_builder import FinancialStatementBuilder
            fs_builder = FinancialStatementBuilder(sim.ledger)
            fs_data = fs_builder.build()
            display_fs = create_display_dataframes(fs_data)

            economic_detective_report(fs_data, params, ledger_df)

            tabs = st.tabs(["📊 損益計算書", "🏦 貸借対照表", "💸 資金収支", "📒 全仕訳"])
            with tabs[0]: st.dataframe(display_fs["pl"], use_container_width=True)
            with tabs[1]: st.dataframe(display_fs["bs"], use_container_width=True)
            with tabs[2]: st.dataframe(display_fs["cf"], use_container_width=True)
            with tabs[3]: st.dataframe(ledger_df, use_container_width=True)

        except Exception as e:
            st.error(f"シミュレーションエラー: {str(e)}")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()

# ============== bkw_sim_amelia1/ui/app.py end