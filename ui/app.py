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
    AdditionalInvestmentParams
)
from core.simulation.simulation import Simulation

# ----------------------------------------------------------------------
# 1. 表示用DataFrame生成（GitHub版完全移植・強化版）
# ----------------------------------------------------------------------
def create_display_dataframes(fs_data: dict) -> dict:
    display_dfs = {}

    def format_cell(val):
        if pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
            return ''
        if isinstance(val, (int, float, np.integer, np.floating)):
            try:
                return f"{int(round(val)):,}"
            except Exception:
                return str(val)
        return str(val)

    for key in ['pl', 'bs', 'cf']:
        if key in fs_data:
            df = fs_data[key].copy()
            df_display = df.reset_index() if df.index.name == '科目' else df.copy()
            num_cols = [c for c in df_display.columns if c.startswith('Year')]
            for col in num_cols:
                df_display[col] = df_display[col].apply(format_cell)
            if '科目' in df_display.columns:
                df_display = df_display.set_index('科目')
            display_dfs[key] = df_display

    return display_dfs

# ----------------------------------------------------------------------
# 2. 財務諸表組み立て（V12 ledger_df 対応版）
# ----------------------------------------------------------------------
def create_financial_statements(ledger_df: pd.DataFrame, holding_years: int) -> dict:
    years_list = list(range(1, holding_years + 1))
    year_index_labels = [f'Year {y}' for y in years_list]

    # --------------------------------------------------
    # ✅ V12形式対応：dr_cr + account → 仮想カラム生成
    # --------------------------------------------------
    if ledger_df is not None and not ledger_df.empty:
        ledger_df = ledger_df.copy()

        ledger_df['dr_account'] = np.where(
            ledger_df['dr_cr'] == 'debit',
            ledger_df.get('account', ''),
            ''
        )
        ledger_df['cr_account'] = np.where(
            ledger_df['dr_cr'] == 'credit',
            ledger_df.get('account', ''),
            ''
        )
        ledger_df['debit_amount'] = np.where(
            ledger_df['dr_cr'] == 'debit',
            ledger_df['amount'],
            0
        )
        ledger_df['credit_amount'] = np.where(
            ledger_df['dr_cr'] == 'credit',
            ledger_df['amount'],
            0
        )

        debit_total = ledger_df['debit_amount'].sum()
        credit_total = ledger_df['credit_amount'].sum()
    else:
        debit_total = credit_total = 0.0

    balance_diff = abs(debit_total - credit_total)
    is_balanced = balance_diff < 1.0

    def make_fs_df(rows):
        df = pd.DataFrame(0.0, index=rows, columns=year_index_labels).astype("Float64")
        df.index.name = '科目'
        return df

    # --------------------------------------------------
    # 科目定義（GitHub版完全復元）
    # --------------------------------------------------
    pl_rows = [
        '売上高', '売上総利益',
        '建物減価償却費', '追加設備減価償却費',
        '租税公課（消費税)', '租税公課（固定資産税)',
        '販売費一般管理費', '営業利益',
        '当座借越利息', '初期長借利息',
        '追加設備長借利息', '運転資金借入金利息',
        'その他営業外費用',
        '経常利益', '特別利益',
        '税引前当期利益', '所得税', '当期利益'
    ]

    bs_rows = [
        '預金', '初期建物', '建物減価償却累計額',
        '追加設備', '追加設備減価償却累計額',
        '土地', '資産合計',
        '未払所得税', '当座借越',
        '初期投資長期借入金', '追加設備長期借入金',
        '運転資金借入金',
        '繰越利益剰余金', '元入金', '負債・元入金合計'
    ]

    cf_rows = [
        '【営業収支】', '現金売上', '営業収入計',
        '現金仕入', '固定資産税', '販売費一般管理費',
        '未払消費税納付', '未払所得税納付',
        '当座借越利息', '初期長借利息',
        '追加設備長期借入金利息', '運転資金借入金利息',
        'その他営業外費用',
        '営業支出計', '営業収支',
        '【設備収支】', '土地・建物・追加設備売却',
        '設備売却計', '売却費用',
        '土地購入', '初期建物購入', '追加設備購入',
        '設備購入計', '設備収支',
        '【財務収支】',
        '元入金', '当座借越',
        '初期投資長期借入金', '追加設備長期借入金',
        '運転資金借入金',
        '資金調達計',
        '当座借越返済', '初期投資長期借入金返済',
        '追加設備長期借入金返済', '運転資金借入金返済',
        '借入金返済計',
        '財務収支', '【資金収支尻】'
    ]

    pl_df = make_fs_df(pl_rows)
    bs_df = make_fs_df(bs_rows)
    cf_df = make_fs_df(cf_rows)

    # 実効税率（営業利益用・暫定固定）
    effective_tax_rate = 0.30

    # --------------------------------------------------
    # PL / BS 計算
    # --------------------------------------------------
    for y in years_list:
        label = f'Year {y}'
        y_df = ledger_df[ledger_df['year'] == y] if 'year' in ledger_df.columns else ledger_df
        all_until_y = ledger_df[ledger_df['year'] <= y] if 'year' in ledger_df.columns else ledger_df

        # PL（V12対応：仮想カラム使用）
        pl_df.loc['売上高', label] = y_df[y_df['cr_account'] == '売上高']['amount'].sum()
        pl_df.loc['建物減価償却費', label] = y_df[y_df['dr_account'] == '建物減価償却費']['amount'].sum()
        pl_df.loc['追加設備減価償却費', label] = y_df[y_df['dr_account'] == '追加設備減価償却費']['amount'].sum()
        pl_df.loc['租税公課（固定資産税)', label] = y_df[y_df['dr_account'] == '租税公課（固定資産税)']['amount'].sum()
        pl_df.loc['販売費一般管理費', label] = y_df[y_df['dr_account'] == '販売費一般管理費']['amount'].sum()
        pl_df.loc['初期長借利息', label] = y_df[y_df['dr_account'] == '初期長借利息']['amount'].sum()

        pl_df.loc['売上総利益', label] = pl_df.loc['売上高', label]
        pl_df.loc['営業利益', label] = (
            pl_df.loc['売上総利益', label]
            - pl_df.loc['建物減価償却費', label]
            - pl_df.loc['追加設備減価償却費', label]
            - pl_df.loc['販売費一般管理費', label]
            - pl_df.loc['租税公課（固定資産税)', label]
        )

        pl_df.loc['経常利益', label] = (
            pl_df.loc['営業利益', label]
            - pl_df.loc['初期長借利息', label]
        )

        pre_tax_profit = pl_df.loc['経常利益', label]
        tax_amount = max(0, pre_tax_profit * effective_tax_rate)

        pl_df.loc['税引前当期利益', label] = pre_tax_profit
        pl_df.loc['所得税', label] = tax_amount
        pl_df.loc['当期利益', label] = pre_tax_profit - tax_amount

        # BS（簡易）
        dr_cash = all_until_y[all_until_y['dr_account'] == '預金']['amount'].sum()
        cr_cash = all_until_y[all_until_y['cr_account'] == '預金']['amount'].sum()
        bs_df.loc['預金', label] = dr_cash - cr_cash
        bs_df.loc['未払所得税', label] = pl_df.loc['所得税', label]

    return {
        'pl': pl_df,
        'bs': bs_df,
        'cf': cf_df,
        'is_balanced': is_balanced,
        'debit_total': debit_total,
        'credit_total': credit_total,
        'balance_diff': balance_diff
    }


# ----------------------------------------------------------------------
# 3. V12完全互換サイドバー（6セクション・holding_years internal）
# ----------------------------------------------------------------------
def setup_sidebar() -> SimulationParams:
    CURRENCY = "%.0f"
    st.sidebar.markdown("## 🛠 ユーザー入力欄")

    # 1. 物件情報（完全復元）
    st.sidebar.header("🏠 1. 物件情報")
    start_date = st.sidebar.date_input("シミュレーション開始日", value=datetime.date(2025, 1, 1), key='sim_start_date')
    price_bld = st.sidebar.number_input("建物価格（税込）", 0.0, value=50_000_000.0, step=100_000.0, format=CURRENCY)
    price_land = st.sidebar.number_input("土地価格", 0.0, value=30_000_000.0,
    step=100_000.0, format=CURRENCY)
    brokerage_fee = st.sidebar.number_input("仲介手数料（税込）", 0.0, value=3_300_000.0, step=10_000.0, format=CURRENCY)

    # 2. 資金調達（完全復元）
    st.sidebar.header("💰 2. 資金調達")
    loan_amount = st.sidebar.number_input("初期借入金額", 0.0, value=70_000_000.0, step=100_000.0, format=CURRENCY)
    loan_years = st.sidebar.number_input("返済期間（年）", 1.0, 50.0, value=30.0, format=CURRENCY)
    loan_rate = st.sidebar.number_input("借入金利（年率 %）", 0.0, 50.0, value=2.5, step=0.01) / 100

    initial_loan = (
        LoanParams(amount=loan_amount, interest_rate=loan_rate, years=int(loan_years)) 
        if loan_amount > 0 else None
    )
    total_investment = price_bld + price_land + brokerage_fee
    equity = max(total_investment - loan_amount, 0.0)
    st.sidebar.metric("元入金（自動計算）", f"{equity:,.0f}")

    # 3. 収益・費用（完全復元）
    st.sidebar.header("🏢 3. 収益・費用")
    annual_rent = st.sidebar.number_input("年間家賃収入（税込）", 0.0, value=3_600_000.0, step=10_000.0, format=CURRENCY)
    mgmt_fee = st.sidebar.number_input("年間管理費（税込）", 0.0, value=1_200_000.0, step=10_000.0, format=CURRENCY)
    repair_cost = st.sidebar.number_input("年間修繕費（税込）", 0.0, value=300_000.0, step=10_000.0, format=CURRENCY)
    insurance = st.sidebar.number_input("年間保険料（非課税）", 0.0, value=100_000.0, step=10_000.0, format=CURRENCY)
    fa_tax_land = st.sidebar.number_input("固定資産税（土地）", 0.0, value=150_000.0, step=10_000.0, format=CURRENCY)
    fa_tax_bld = st.sidebar.number_input("固定資産税（建物）", 0.0, value=150_000.0, step=10_000.0, format=CURRENCY)

    # 4. 税率（完全復元）
    st.sidebar.header("📊 4. 税率")
    vat_rate = st.sidebar.number_input("消費税率（%）", 0.0, 50.0, value=10.0) / 100
    overdraft_rate = st.sidebar.number_input("当座借越金利（%）", 0.0, 50.0, value=5.0) / 100

    # 5. 出口設定（holding_years内部生成源）
    st.sidebar.header("📉 5. 出口設定")
    exit_year = st.sidebar.number_input("売却予定年（シミュレーション年数）", min_value=1.0, max_value=50.0, value=5.0, step=1.0, format=CURRENCY)
    holding_years_internal = int(exit_year)  # ★ 内部生成

    selling_price = st.sidebar.number_input("売却価格", 0.0, value=0.0, step=100_000.0, format=CURRENCY)
    selling_cost = st.sidebar.number_input("売却費用", 0.0, value=0.0, step=100_000.0, format=CURRENCY)
    income_tax_rate = st.sidebar.number_input("売却益税率（%）", 1.0, 60.0, value=30.0) / 100

    exit_params = ExitParams(
        exit_year=holding_years_internal,
        selling_price=selling_price,
        selling_cost=selling_cost,
        income_tax_rate=income_tax_rate
    )

    # 6. 追加投資（V12完全復元：最大5回）
    st.sidebar.header("➕ 6. 追加投資")
    additional_investments: List[AdditionalInvestmentParams] = []

    for i in range(1, 6):
        with st.sidebar.expander(f"第{i}回 追加投資"):
            amt = st.number_input(f"投資額", key=f"inv_amt_{i}", min_value=0.0, step=100_000.0, format=CURRENCY)
            if amt > 0:
                year = st.number_input("投資年", min_value=2.0, max_value=exit_year, value=2.0, step=1.0, format=CURRENCY)
                dep = st.number_input("償却年数", min_value=1.0, max_value=50.0, value=15.0, step=1.0, format=CURRENCY)
                additional_investments.append(
                    AdditionalInvestmentParams(
                        invest_year=int(year),
                        invest_amount=amt,
                        depreciation_years=int(dep),
                        loan_amount=0.0,
                        loan_years=0,
                        loan_interest_rate=0.0
                    )
                )

    # SimulationParams生成（V12完全互換＋holding_years internal）
    return SimulationParams(
        property_price_building=price_bld,
        property_price_land=price_land,
        brokerage_fee_amount_incl=brokerage_fee,
        building_useful_life=47,
        building_age=5,
        holding_years=holding_years_internal,  # ★ internal生成値使用
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
        start_date=start_date
    )

# ----------------------------------------------------------------------
# 4. 経済探偵レポート（GitHub版完全移植）
# ----------------------------------------------------------------------
def economic_detective_report(fs_data: dict, params: SimulationParams, ledger_df: pd.DataFrame):
    st.subheader("🕵️‍♂️ 経済探偵の分析レポート")
    
    st.markdown("""
        <style>
        .report-card { 
            background-color: #f8f9fa; 
            border-left: 5px solid #2c3e50; 
            padding: 10px 15px; 
            margin-bottom: 10px; 
            border-radius: 4px; 
            display: flex; 
            flex-direction: column; 
        }
        .report-label { font-size: 0.85rem; color: #666; font-weight: bold; }
        .report-value { font-size: 1.25rem; color: #2c3e50; font-weight: 800; }
        </style>
    """, unsafe_allow_html=True)

    # 指標計算（ledgerから実データ取得）
    total_rent = fs_data['pl'].loc['売上高'].sum() if '売上高' in fs_data['pl'].index else 0
    total_mgmt = fs_data['pl'].loc['販売費一般管理費'].sum() if '販売費一般管理費' in fs_data['pl'].index else 0
    total_tax = fs_data['pl'].loc['所得税'].sum() if '所得税' in fs_data['pl'].index else 0
    final_cash = fs_data['bs'].loc['預金'].iloc[-1] if '預金' in fs_data['bs'].index else 0
    add_inv_total = sum(i.invest_amount for i in params.additional_investments)
    
    def metric_html(label, value):
        return f'<div class="report-card"><span class="report-label">{label}</span><span class="report-value">{value}</span></div>'

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(metric_html("1. 総家賃収入", f"{int(total_rent):,} 円"), unsafe_allow_html=True)
        st.markdown(metric_html("2. 総管理費", f"{int(total_mgmt):,} 円"), unsafe_allow_html=True)
        st.markdown(metric_html("3. 期間中所得税総額", f"{int(total_tax):,} 円"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_html("4. 運用期間末預金残高", f"{int(final_cash):,} 円"), unsafe_allow_html=True)
        st.markdown(metric_html("5. 追加投資総額", f"{int(add_inv_total):,} 円"), unsafe_allow_html=True)
        st.markdown(metric_html("6. 保有期間", f"{params.holding_years} 年"), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 5. メイン（GitHub版UI + V12互換 + 拡張タブ）
# ----------------------------------------------------------------------
def main():
    st.set_page_config(layout="wide", page_title="BKW Invest Sim (Amelia V20統合版)")
    st.title("💰 BKW 不動産投資シミュレーション (V20: UI+ロジック完全統合版)")

    params = setup_sidebar()
    run_clicked = st.button("▶︎ シミュレーション実行", type="primary")

    if run_clicked:
        try:
            # V12互換のSimulation実行
            sim = Simulation(params, params.start_date)
            sim.run()
            ledger_df = sim.ledger.get_df()

            # 財務諸表生成（GitHub版ロジック）
            fs_data = create_financial_statements(ledger_df, params.exit_params.exit_year)
            display_fs = create_display_dataframes(fs_data)

            # 簿記検証（両バージョン対応）
            if fs_data['is_balanced']:
                st.success(f"✅ 簿記検証：正常（借方・貸方一致：{int(fs_data['debit_total']):,}）")
            else:
                st.error(f"❌ 簿記検証：不一致（差額：{fs_data['balance_diff']:,.0f}）")

            # GitHub版：経済探偵レポート
            economic_detective_report(fs_data, params, ledger_df)

            # 拡張タブ構成
            tabs = st.tabs(["📋 前提条件確認", "📊 財務三表", "📒 全仕訳データ"])
            
            with tabs[0]:
                st.subheader("シミュレーション前提条件")
                summary_data = {
                    "建物価格": params.property_price_building,
                    "土地価格": params.property_price_land,
                    "仲介手数料": params.brokerage_fee_amount_incl,
                    "元入金": params.initial_equity,
                    "年間家賃収入": params.annual_rent_income_incl,
                    "管理費": params.annual_management_fee_initial,
                    "固定資産税（土地）": params.fixed_asset_tax_land,
                    "固定資産税（建物）": params.fixed_asset_tax_building,
                    "保有年数": params.holding_years,
                    "追加投資件数": len(params.additional_investments)
                }
                summary_df = pd.DataFrame.from_dict(summary_data, orient="index", columns=["金額"])
                summary_df["金額"] = summary_df["金額"].apply(lambda x: f"{int(x):,}" if isinstance(x, (int, float)) else str(x))
                st.table(summary_df)

            with tabs[1]:
                # 3列レイアウトで財務三表
                col1, col2, col3 = st.columns(3)
                with col1: 
                    st.subheader("損益計算書（PL）")
                    st.dataframe(display_fs['pl'], use_container_width=True)
                with col2: 
                    st.subheader("貸借対照表（BS）")
                    st.dataframe(display_fs['bs'], use_container_width=True)
                with col3: 
                    st.subheader("キャッシュフロー（CF）")
                    st.dataframe(display_fs['cf'], use_container_width=True)

            with tabs[2]:
                st.subheader("全仕訳（検証用）")
                st.dataframe(ledger_df, use_container_width=True)

        except Exception as e:
            st.error(f"シミュレーションエラー: {str(e)}")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()

# =========== bkw_sim_amelia1/ui/app.py end

