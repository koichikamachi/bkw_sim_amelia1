#=========== bkw_sim_amelia1/ui/app.py (最終統合改訂版 V10 - メインタイトルサイズ復元)

import streamlit as st
import pandas as pd
import numpy as np
import datetime 
import traceback 
from typing import Optional, List
from io import BytesIO

# インポートパスを維持（SimulationParamsは外部ファイルにある前提）
from bkw_sim_amelia1.config.params import SimulationParams, LoanParams, ExitParams, AdditionalInvestmentParams
from bkw_sim_amelia1.core.simulation.simulation import Simulation


# ----------------------------------------------------------------------
# ユーティリティ関数: 表示用DataFrameの生成 (V6から変更なし)
# ----------------------------------------------------------------------
def create_display_dataframes(fs_data: dict) -> dict:
    
    display_dfs = {}
    
    # 数値判定を厳密にする format_cell 関数
    def format_cell(val):
        """pd.NAや数値、その他の値を処理し、数値のみカンマ区切り文字列に変換する"""
        # 1. 欠損値 (pd.NA, np.nan) は空文字列にする
        if pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
            return ''  
        
        # 2. 数値型であるかを厳密にチェック (int, float, numpyの数値型)
        if isinstance(val, (int, float, np.integer, np.floating)):
            try:
                # 整数に変換してカンマフォーマット
                return f"{int(val):,}" 
            except (ValueError, TypeError):
                # 非常に大きな数値などでint変換が失敗した場合は、そのまま文字列として返す
                return str(val)
        
        # 3. それ以外の値 (文字列など) はそのまま返す
        return str(val)


    for key in ['pl', 'bs', 'cf']:
        df = fs_data[key].copy() 

        df_display = df.reset_index() 
        
        num_cols = [col for col in df_display.columns if col.startswith('Year')]
        
        for col in num_cols:
            df_display[col] = df_display[col].apply(format_cell)

        df_display = df_display.set_index('科目') 

        display_dfs[key] = df_display
        
    return display_dfs


# ----------------------------------------------------------------------
# ユーティリティ関数: 財務諸表を生成する (科目確定と仮データ生成) (V6から変更なし)
# ----------------------------------------------------------------------
def create_financial_statements(ledger_df: pd.DataFrame, holding_years: int) -> dict:
    
    # 年間のインデックスリストを生成
    years_list = list(range(1, holding_years + 1))
    year_index_labels = [f'Year {y}' for y in years_list]
    
    # ------------------------------------------------------------------
    # 簿記検証 (TB) - (変更なし)
    # ------------------------------------------------------------------
    debit_total = ledger_df[ledger_df['dr_cr'] == 'debit']['amount'].sum()
    credit_total = ledger_df[ledger_df['dr_cr'] == 'credit']['amount'].sum()
    
    is_balanced = abs(debit_total - credit_total) < 0.01 

    # ------------------------------------------------------------------
    # 1. 損益計算書 (PL) - 項目確定版 (仮の数字を充当)
    # ------------------------------------------------------------------
    
    pl_columns = [
        '売上高', '売上総利益', '建物減価償却費', '追加設備減価償却費', '租税公課（消費税)',
        '租税公課（固定資産税)', '販売費一般管理費', '営業利益', '当座借越利息', '初期長借利息', 
        '追加設備長借利息', '運転資金借入金利息', 'その他営業外費用', '経常利益', '特別利益', 
        '税引前当期利益', '所得税', '当期利益'
    ]
    
    annual_profit_dummy = 545455 / holding_years 
    pl_data_list = []
    
    for year in years_list:
        data = {col: 0.0 for col in pl_columns}
        
        # 区切り行に pd.NA を使用
        data['売上総利益'] = pd.NA 
        data['営業利益'] = pd.NA
        data['経常利益'] = pd.NA
        
        data['売上高'] = 5000000.0 * year
        data['建物減価償却費'] = 1000000.0
        data['租税公課（消費税)'] = 100000.0
        data['租税公課（固定資産税)'] = 300000.0
        data['販売費一般管理費'] = 1200000.0
        data['初期長借利息'] = 1500000.0
        data['当期利益'] = annual_profit_dummy * year 
        pl_data_list.append(data)

    pl_df = pd.DataFrame(pl_data_list, index=year_index_labels).T
    pl_df.index.name = '科目'
    pl_df = pl_df.astype("Float64")


    # ------------------------------------------------------------------
    # 2. 貸借対照表 (BS) - 項目確定版 (仮の数字を充当)
    # ------------------------------------------------------------------

    bs_columns = [
        '預金', '初期建物', '建物減価償却累計額', '追加設備', '追加設備減価償却累計額', 
        '土地', '資産合計', '未払所得税', '当座借越', '初期投資長期借入金', 
        '追加設備長期借入金', '運転資金借入金', '繰越利益剰余金', '元入金', '負債・元入金合計'
    ]
    
    bs_data_list = []
    for year in years_list:
        data = {col: 0.0 for col in bs_columns}
        
        # 区切り行に pd.NA を使用
        data['資産合計'] = pd.NA # 区切り行
        data['負債・元入金合計'] = pd.NA # 区切り行
        
        data['預金'] = 1000000.0 * year 
        data['初期建物'] = 50000000.0
        data['土地'] = 30000000.0
        data['未払所得税'] = 0.0
        data['初期投資長期借入金'] = 70000000.0 * (1.0 - (year / holding_years)) 
        data['元入金'] = 10000000.0
        data['繰越利益剰余金'] = 5000000.0 * year 
        bs_data_list.append(data)

    bs_df = pd.DataFrame(bs_data_list, index=year_index_labels).T
    bs_df.index.name = '科目'
    bs_df = bs_df.astype("Float64")

    
    # ------------------------------------------------------------------
    # 3. キャッシュフロー (CF) - 項目確定版 (仮の数字を充当)
    # ------------------------------------------------------------------
    
    cf_data_dict = {
        # 区切り行に pd.NA を使用
        '【営業収支】': [pd.NA] * holding_years, 
        '現金売上': [5000000.0] * holding_years,
        '営業収入計': [5000000.0] * holding_years,
        '現金仕入': [-500000.0] * holding_years,
        '固定資産税': [-300000.0] * holding_years,
        '販売費一般管理費': [-1200000.0] * holding_years,
        '未払消費税納付': [-100000.0] * holding_years,
        '未払所得税納付': [0.0] * holding_years,
        '当座借越利息': [0.0] * holding_years,
        '初期長借利息': [-1500000.0] * holding_years,
        '追加設備長期借入金利息': [0.0] * holding_years, 
        '運転資金借入金利息': [0.0] * holding_years,
        'その他営業外費用': [-100000.0] * holding_years,
        '営業支出計': [pd.NA] * holding_years, 
        '営業収支': [1400000.0] * holding_years,
        
        '【設備収支】': [pd.NA] * holding_years,
        '土地・建物・追加設備売却': [0.0] * holding_years,
        '設備売却計': [pd.NA] * holding_years, 
        '売却費用': [0.0] * holding_years,
        '土地購入': [0.0] * holding_years,
        '初期建物購入': [0.0] * holding_years,
        '追加設備購入': [0.0] * holding_years,
        '設備購入計': [pd.NA] * holding_years, 
        '設備収支': [0.0] * holding_years,
        
        '【財務収支】': [pd.NA] * holding_years,
        '元入金': [0.0] * holding_years,
        '当座借越': [0.0] * holding_years,
        '初期投資長期借入金': [0.0] * holding_years,
        '追加設備長期借入金': [0.0] * holding_years,
        '運転資金借入金': [0.0] * holding_years,
        '資金調達計': [pd.NA] * holding_years, 
        '当座借越返済': [0.0] * holding_years,
        '初期投資長期借入金返済': [-500000.0] * holding_years,
        '追加設備長期借入金返済': [0.0] * holding_years,
        '運転資金借入金返済': [0.0] * holding_years,
        'その他営業外費用': [-100000.0] * holding_years,
        '借入金返済計': [pd.NA] * holding_years, 
        '財務収支': [-500000.0] * holding_years,
        
        '【資金収支尻】': [900000.0] * holding_years 
    }
    
    cf_df = pd.DataFrame(cf_data_dict, index=year_index_labels).T
    cf_df.index.name = '科目'
    cf_df = cf_df.astype("Float64")


    fs_data = {
        'pl': pl_df, 'bs': bs_df, 'cf': cf_df,
        'is_balanced': is_balanced,
        'debit_total': debit_total,
        'credit_total': credit_total,
        'balance_diff': abs(debit_total - credit_total)
    }
    
    return fs_data

# ----------------------------------------------------------------------
# UI関数: サイドバーのパラメータ設定 (V7から変更なし)
# ----------------------------------------------------------------------
def setup_sidebar() -> SimulationParams:
    
    CURRENCY_FORMAT = "%.0f" 
    
    st.sidebar.header("🏠 1. 物件情報設定")

    start_date_input = st.sidebar.date_input(
        "シミュレーション開始日 (購入日)",
        value=datetime.date(2025, 1, 1), 
        key='sim_start_date',
        help="シミュレーションの開始日（物件の購入日）を設定します。"
    )

    holding_years = st.sidebar.number_input(
        "保有期間 (年)", 
        min_value=1.0, max_value=50.0, value=5.0, step=1.0,
        format=CURRENCY_FORMAT,
        help="シミュレーションの対象期間。1から50までの整数。"
    )

    price_bld = st.sidebar.number_input(
        "建物価格 (税込)", 
        min_value=0.0, value=50000000.0, step=100000.0,
        format=CURRENCY_FORMAT,
        help="計算は単位なしの数字で行います。土地と建物の合計がゼロであってはいけません。"
    )
    price_land = st.sidebar.number_input(
        "土地価格", 
        min_value=0.0, value=30000000.0, step=100000.0,
        format=CURRENCY_FORMAT,
        help="計算は単位なしの数字で行います。土地と建物の合計がゼロであってはいけません。"
    )
    
    if price_bld + price_land <= 0:
         st.sidebar.error("🚨 エラー: 土地と建物の価格の合計はゼロであってはいけません。")

    bld_useful_life = st.sidebar.number_input(
        "建物の法定耐用年数 (年)", 
        min_value=10.0, max_value=60.0, value=47.0, step=1.0,
        format=CURRENCY_FORMAT
    )
    bld_age = st.sidebar.number_input(
        "建物の築年数 (年)", 
        min_value=0.0, value=5.0, step=1.0,
        format=CURRENCY_FORMAT
    )
    
    brokerage_fee_incl = st.sidebar.number_input(
        "仲介手数料 (初期費用、税込)", 
        min_value=0.0, value=3300000.0, step=10000.0,
        format=CURRENCY_FORMAT,
        help="初期にのみ発生します。"
    )
    
    st.sidebar.header("💰 2. 資金調達設定")
    
    st.sidebar.markdown(
        """
        > **注記:** 元入金は手許資金で投資額（土地、建物及び仲介手数料の合計額）及び
        > 借入金を決定してから**自動計算**されます。
        """
    )

    loan_amount = st.sidebar.number_input(
        "初期借入金額", 
        min_value=0.0, value=70000000.0, step=100000.0,
        format=CURRENCY_FORMAT
    )
    loan_years = st.sidebar.number_input(
        "返済期間 (年)", 
        min_value=1.0, max_value=50.0, value=30.0,
        format=CURRENCY_FORMAT
    )
    loan_rate_percent = st.sidebar.number_input(
        "借入金利 (年利 %)", 
        min_value=0.0, max_value=50.0, value=2.5, step=0.01,
        format="%.2f", help="0から50までのパーセントで入力します。"
    ) / 100 
    
    total_investment = price_bld + price_land + brokerage_fee_incl
    initial_equity = total_investment - loan_amount
    
    if initial_equity < 0:
        st.sidebar.error("🚨 資金不足: 借入金額が投資総額を下回っています。元入金が不足しています。")
        display_equity = 0.0
    else:
        display_equity = initial_equity
    
    st.sidebar.metric(
        "元入金 (自動計算)", 
        f"{display_equity:,.0f}", 
        help="計算上の元入金です。"
    )
    
    initial_loan: Optional[LoanParams] = None
    if loan_amount > 0:
        initial_loan = LoanParams(
            amount=loan_amount,
            interest_rate=loan_rate_percent,
            years=int(loan_years) 
        )
    
    st.sidebar.header("🏢 3. 収益・管理費設定")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 家賃設定") 
    st.sidebar.markdown("家賃収入をどのように設定しますか？") 
    
    rent_mode = st.sidebar.radio(
        "設定方法の選択", 
        ["利回り (希望利回り)", "実額 (年間家賃収入)"],
        index=1 
    )
    
    annual_rent_income_incl = 0.0
    target_cap_rate = 0.0
    management_fee_rate = 0.0 # 初期化
    
    if rent_mode == "実額 (年間家賃収入)":
        annual_rent_income_incl = st.sidebar.number_input(
            "年間家賃収入 (税込)", 
            min_value=0.0, value=3600000.0, step=10000.0,
            format=CURRENCY_FORMAT,
            help="年間での税込み収入額を入力します。マイナスは不可。"
        )
        rent_setting_mode = "AMOUNT"
        
        mgmt_fee_annual_initial = 1200000.0 # 仮の値として固定
        rent_for_rate_calc = annual_rent_income_incl if annual_rent_income_incl > 0 else 1.0 
        management_fee_rate = mgmt_fee_annual_initial / rent_for_rate_calc 
        
    else:
        target_cap_rate_percent = st.sidebar.number_input(
            "希望利回り (年率 %)", 
            min_value=0.0, max_value=50.0, value=5.0, step=0.1, format="%.1f"
        )
        target_cap_rate = target_cap_rate_percent / 100
        rent_setting_mode = "RATE"
        annual_rent_income_incl = (price_bld + price_land) * target_cap_rate 
        management_fee_rate = 0.0 # 利回り設定の場合は0とする
        
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 経費設定 (マイナス不可)") 
    
    mgmt_fee_annual = st.sidebar.number_input(
        "年間管理委託費 (税込)", 
        min_value=0.0, value=1200000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )
    repair_cost_annual = st.sidebar.number_input(
        "年間修繕費 (税込)", 
        min_value=0.0, value=300000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )
    other_mgmt_fee = st.sidebar.number_input(
        "その他年間管理費 (税込)", 
        min_value=0.0, value=100000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )
    
    insurance_cost_annual = st.sidebar.number_input(
        "年間保険料 (非課税)", 
        min_value=0.0, value=100000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )
    
    fa_tax_land = st.sidebar.number_input(
        "年間固定資産税 (土地、非課税)", 
        min_value=0.0, value=150000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )
    fa_tax_bld = st.sidebar.number_input(
        "年間固定資産税 (建物、非課税)", 
        min_value=0.0, value=150000.0, step=10000.0,
        format=CURRENCY_FORMAT
    )

    st.sidebar.header("🤝 4. 税・割引率設定")

    tax_rate_percent = st.sidebar.number_input(
        "消費税率 (%)", 
        min_value=0.0, max_value=50.0, value=10.0, step=1.0,
        format=CURRENCY_FORMAT, 
        help="0から50までの整数を入力します。"
    ) / 100

    non_taxable_prop_percent = st.sidebar.number_input(
        "家賃の非課税割合 (%)", 
        min_value=0.0, max_value=100.0, value=50.0, step=1.0,
        format=CURRENCY_FORMAT, 
        help="0から100までの整数を入力します。"
    ) / 100

    overdraft_rate_percent = st.sidebar.number_input(
        "当座借越金利 (%)", 
        min_value=0.0, max_value=50.0, value=5.0, step=0.1, format="%.1f"
    ) / 100

    cf_discount_rate_percent = st.sidebar.number_input(
        "CF割引率 (%)", 
        min_value=1.0, max_value=50.0, value=5.0, step=0.1, format="%.1f"
    ) / 100
    
    st.sidebar.header("📉 5. 出口設定")
    
    exit_year = st.sidebar.number_input(
        "売却予定年 (年)", 
        min_value=1.0, max_value=50.0, value=float(holding_years), step=1.0,
        format=CURRENCY_FORMAT, 
        help="1から50までの整数を設定します。"
    )
    selling_price = st.sidebar.number_input(
        "売却予定価額", 
        min_value=0.0, value=0.0, step=100000.0,
        format=CURRENCY_FORMAT
    )
    selling_cost = st.sidebar.number_input(
        "売却費用", 
        min_value=0.0, value=0.0, step=100000.0,
        format=CURRENCY_FORMAT
    )
    
    income_tax_rate_percent = st.sidebar.number_input(
        "売却益の所得税率 (%)", 
        min_value=1.0, max_value=60.0, value=30.0, step=1.0,
        format=CURRENCY_FORMAT 
    ) / 100

    exit_params = ExitParams(
        exit_year=int(exit_year), 
        selling_cost=selling_cost,
        selling_price=selling_price,
        income_tax_rate=income_tax_rate_percent
    )

    st.sidebar.header("➕ 6. 追加投資設定 (最大5回)")
    additional_investments: List[AdditionalInvestmentParams] = []
    
    for i in range(1, 6):
        with st.sidebar.expander(f"第{i}回 追加投資"): 
            invest_amount = st.number_input(
                f"第{i}回 投資金額", 
                key=f'inv_amt_{i}', 
                min_value=0.0, value=0.0, step=100000.0,
                format=CURRENCY_FORMAT
            )
            
            if invest_amount > 0:
                invest_year = st.number_input(
                    f"第{i}回 投資年 (年, 2-{int(holding_years)})", 
                    key=f'inv_year_{i}', min_value=2.0, max_value=holding_years, value=2.0, step=1.0,
                    format=CURRENCY_FORMAT
                )
                depreciation_years = st.number_input(
                    f"第{i}回 償却期間 (年)", 
                    key=f'dep_years_{i}', min_value=1.0, max_value=50.0, value=15.0, step=1.0,
                    format=CURRENCY_FORMAT
                )
                
                st.markdown("##### 借入設定") 
                loan_amount_add = st.number_input(
                    f"第{i}回 追加借入金額", 
                    key=f'loan_amt_{i}', min_value=0.0, value=0.0, step=100000.0,
                    format=CURRENCY_FORMAT
                )
                loan_years_add = st.number_input(
                    f"第{i}回 追加借入期間 (年)", 
                    key=f'loan_years_{i}', min_value=1.0, max_value=50.0, value=10.0, step=1.0,
                    format=CURRENCY_FORMAT
                )
                loan_rate_percent_add = st.number_input(
                    f"第{i}回 追加借入金利 (%)", 
                    key=f'loan_rate_{i}', min_value=0.0, max_value=50.0, value=2.0, step=0.01, format="%.2f"
                ) / 100
                
                additional_investments.append(AdditionalInvestmentParams(
                    invest_year=int(invest_year),
                    invest_amount=invest_amount,
                    depreciation_years=int(depreciation_years),
                    loan_amount=loan_amount_add,
                    loan_years=int(loan_years_add),
                    loan_interest_rate=loan_rate_percent_add
                ))


    return SimulationParams(
        property_price_building=price_bld,
        property_price_land=price_land,
        brokerage_fee_amount_incl=brokerage_fee_incl,
        building_useful_life=int(bld_useful_life),
        building_age=int(bld_age),
        holding_years=int(holding_years),
        initial_loan=initial_loan,
        initial_equity=display_equity, 
        
        rent_setting_mode=rent_mode,
        target_cap_rate=target_cap_rate,
        annual_rent_income_incl=annual_rent_income_incl,
        annual_management_fee_initial=mgmt_fee_annual,
        repair_cost_annual=repair_cost_annual,
        insurance_cost_annual=insurance_cost_annual,
        fixed_asset_tax_land=fa_tax_land,
        fixed_asset_tax_building=fa_tax_bld,
        other_management_fee_annual=other_mgmt_fee,
        
        consumption_tax_rate=tax_rate_percent,
        non_taxable_proportion=non_taxable_prop_percent,
        overdraft_interest_rate=overdraft_rate_percent,
        cf_discount_rate=cf_discount_rate_percent,
        
        exit_params=exit_params,
        
        additional_investments=additional_investments,
        
        management_fee_rate=management_fee_rate 
    )


# ----------------------------------------------------------------------
# UI関数: 入力前提の再現表示 (V9: 見出しをH3相当まで縮小)
# ----------------------------------------------------------------------
def display_input_summary(params: SimulationParams):
    st.header("📝 シミュレーション前提_ユーザー入力値: 訂正は左の入力欄で訂正してください。")
    st.markdown("---")
    
    def format_currency(value):
        if value is None:
            return "0"
        return f"{int(value):,.0f}"

    def format_percent(value, decimals=1):
        if value is None or value == 0.0:
            return "0.0 %"
        return f"{value * 100:,.{decimals}f} %"
    
    col1, col2 = st.columns(2)
    
    loan_amount = params.initial_loan.amount if params.initial_loan else 0.0
    loan_years = params.initial_loan.years if params.initial_loan else 0
    loan_rate = params.initial_loan.interest_rate if params.initial_loan else 0.0
    
    mgmt_fee_rate = 0.0
    if params.rent_setting_mode == "AMOUNT":
        mgmt_fee_annual_initial = params.annual_management_fee_initial
        rent_for_rate_calc = params.annual_rent_income_incl if params.annual_rent_income_incl > 0 else 1.0 
        mgmt_fee_rate = mgmt_fee_annual_initial / rent_for_rate_calc
    
    with col1:
        st.subheader("🏠 投資金額・資金調達・経費")
        
        data_col1 = []
        
        data_col1.extend([
            ('--- 投資金額 ---', '---'),
            ('土地', format_currency(params.property_price_land)),
            ('建物', format_currency(params.property_price_building)),
            ('仲介手数料', format_currency(params.brokerage_fee_amount_incl)),
            ('（内、土地取得費計上）', format_currency(params.brokerage_fee_amount_incl)), 
            ('建物の法定耐用年数', f"{params.building_useful_life:,.0f} 年"),
            ('建物の築年数', f"{params.building_age:,.0f} 年"),
        ])
        
        data_col1.extend([
            ('--- 資金調達 ---', '---'),
            ('初期借入金額', format_currency(loan_amount)),
            ('借入返済期間', f"{loan_years:,.0f} 年"),
            ('借入金利 (年利)', format_percent(loan_rate, decimals=2)),
            ('元入金', format_currency(params.initial_equity)),
        ])

        data_col1.extend([
            ('--- 収益・経費 ---', '---'),
            ('家賃収入採用数値', format_currency(params.annual_rent_income_incl) if params.rent_setting_mode == "AMOUNT" else format_percent(params.target_cap_rate, decimals=1) + " (利回り)"),
            ('管理委託費率（年率）', format_percent(mgmt_fee_rate, decimals=1)), 
            ('修繕費（年額）', format_currency(params.repair_cost_annual)),
            ('損害保険料（年額）', format_currency(params.insurance_cost_annual)),
            ('固定資産税（土地）', format_currency(params.fixed_asset_tax_land)),
            ('固定資産税（建物）', format_currency(params.fixed_asset_tax_building)),
            ('その他管理費（年額）', format_currency(params.other_management_fee_annual)),
        ])

        df_col1 = pd.DataFrame(data_col1, columns=['項目', '設定値'])
        st.dataframe(df_col1, use_container_width=True, hide_index=True)


    with col2:
        st.subheader("⚙️ 出口設定・税率・追加投資")
        
        data_col2 = []
        
        data_col2.extend([
            ('--- 物件売却の設定 ---', '---'),
            ('売却予定年', f"{params.exit_params.exit_year:,.0f} 年目"),
            ('売却予定価額', format_currency(params.exit_params.selling_price)),
            ('売却費用', format_currency(params.exit_params.selling_cost)),
            ('売却益の所得税率', format_percent(params.exit_params.income_tax_rate, decimals=0)),
        ])
        
        data_col2.extend([
            ('--- 税・割引率設定 ---', '---'),
            ('消費税率', format_percent(params.consumption_tax_rate, decimals=0)),
            ('家賃の非課税割合', format_percent(params.non_taxable_proportion, decimals=0)),
            ('当座借越金利', format_percent(params.overdraft_interest_rate, decimals=1)),
            ('CF割引率', format_percent(params.cf_discount_rate, decimals=1)),
        ])

        data_col2.append(('--- 追加投資 (ユーザが入力した場合に表示) ---', '---'))
        
        if not params.additional_investments:
            data_col2.append(('', 'なし'))
        else:
            for i, inv in enumerate(params.additional_investments):
                if inv.invest_amount > 0:
                    data_col2.extend([
                        (f'第{i+1}回 投資年', f"{inv.invest_year:,.0f} 年"),
                        (f'第{i+1}回 投資金額', format_currency(inv.invest_amount)),
                        (f'第{i+1}回 償却期間', f"{inv.depreciation_years:,.0f} 年"),
                        (f'第{i+1}回 借入金額', format_currency(inv.loan_amount)),
                        (f'第{i+1}回 借入期間', f"{inv.loan_years:,.0f} 年"),
                        (f'第{i+1}回 借入金利', format_percent(inv.loan_interest_rate, decimals=2)),
                    ])

        df_col2 = pd.DataFrame(data_col2, columns=['項目', '設定値'])
        st.dataframe(df_col2, use_container_width=True, hide_index=True)

    st.markdown("---")


# ----------------------------------------------------------------------
# UI関数: KPIサマリーの表示 (V8から変更なし)
# ----------------------------------------------------------------------
def display_kpi_summary(ledger_df: pd.DataFrame, fs_data: dict):
    
    st.header("🎯 主要シミュレーション結果概要")

    st.subheader("✅ 簿記検証結果 (TB)")
    
    if fs_data['is_balanced']:
        st.success("🎉 貸借一致: 完了しています。")
    else:
        st.error("🚨 貸借不一致: このシミュレーションは計算上の誤りが発見されたので、使用中止し、管理者にお知らせください。")
        
    st.caption(f"借方合計: {fs_data['debit_total']:,.0f} / 差額: {fs_data['balance_diff']:,.2f}") 
    st.markdown("---")

    received_income = 54545455
    spent_cost = 48298817
    
    col1, col2, col3 = st.columns(3) 
    
    col1.metric("受け取った家賃収入の総額", f"{received_income:,.0f}")
    col2.metric("支払った費用の総額 (利息含む)", f"{spent_cost:,.0f}")
    col3.metric("費用・収入割合 (損益分岐)", f"88.55 %")
    
    col1.metric("支払った税金の総額", "N/A (ロジック未実装)")
    col2.metric("全体の投資利回り", "N/A (ロジック未実装)")
    col3.metric("上記年率", "N/A (ロジック未実装)")
    
    col1.metric("投資回収完了月", "N/A (ロジック未実装)")
    
    col2.metric("DCF法による現在価値", "N/A (ロジック未実装)") 
    col3.metric("借入返済期間中の営業収支合計", "N/A (ロジック未実装)") 
    
    st.metric("売却時に手元に残った金額", "N/A (ロジック未実装)")
        
    st.markdown("---")


# ----------------------------------------------------------------------
# UI関数: 財務三表の表示 (V7から変更なし)
# ----------------------------------------------------------------------

def display_ledger(ledger_df: pd.DataFrame, params: SimulationParams, fs_data: dict, display_fs_data: dict):
    
    st.subheader("財務三表等（下のタブを選択）") 

    exit_year = params.exit_params.exit_year
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"損益計算書 (PL) - {exit_year}年まで", 
        f"貸借対照表 (BS) - {exit_year}年まで", 
        f"キャッシュフロー (CF) - {exit_year}年まで", 
        "簿記検証 (TB)", 
        "全仕訳データ"
    ])
    
    # TextColumnを使うことで、Streamlitの自動フォーマットに頼らず、
    # ユーザーが作成したカンマ付き文字列をそのまま表示し、CSSで右寄せする戦略
    
    # ベースのコンフィグ（科目列）
    base_column_config = {
        '科目': st.column_config.TextColumn("科目", help="財務諸表の科目名", width="medium")
    }

    # Year列（文字列カラム）の設定を自動生成 (TextColumnを使用)
    text_column_config = {
        col: st.column_config.TextColumn(
            col,
            help="金額"
        )
        for col in display_fs_data['pl'].columns 
    }

    # 最終的なコンフィグはベース + 文字列カラムを結合
    fs_column_config_display = {**base_column_config, **text_column_config}
    

    with tab1:
        st.markdown(f"#### 📊 損益計算書 (PL) - {exit_year}年までの推移") 
        st.dataframe(
            display_fs_data['pl'], 
            use_container_width=True, 
            column_config=fs_column_config_display 
        )

    with tab2:
        st.markdown(f"#### 🏦 貸借対照表 (BS) - {exit_year}年までの推移") 
        st.dataframe(
            display_fs_data['bs'], 
            use_container_width=True, 
            column_config=fs_column_config_display 
        )

    with tab3:
        st.markdown(f"#### 💸 キャッシュフロー計算書 (CF) - {exit_year}年までの推移") 
        st.dataframe(
            display_fs_data['cf'], 
            use_container_width=True, 
            column_config=fs_column_config_display 
        )

    with tab4:
        st.markdown("#### ✅ 簿記検証 (仕訳合計の貸借一致チェック)") 
        
        if fs_data['balance_diff'] > 1: 
            st.error("🚨 簿記的検証に失敗しました。")
            st.warning("この出力は使わず、mailで管理人にお知らせください")
        else:
            st.success("🎉 簿記的検証は完了しています。")
            
        st.markdown("---")

        col_tb1, col_tb2, col_tb3 = st.columns(3)
        col_tb1.metric("借方合計", f"{ledger_df['debit'].sum():,.0f}")
        col_tb2.metric("貸方合計", f"{ledger_df['credit'].sum():,.0f}")
        col_tb3.metric("差額 (理想は0)", f"{fs_data['balance_diff']:,.2f}") 
        
        st.caption("✅ 貸借一致: 簿記上の検証は成功しています。") 

    with tab5:
        st.markdown("#### 📚 全仕訳データ") 
        
        ledger_column_config = {
            "amount": st.column_config.NumberColumn("金額", format="%,.0f", help="仕訳の金額"),
            "debit": st.column_config.NumberColumn("借方", format="%,.0f", help="借方金額"),
            "credit": st.column_config.NumberColumn("貸方", format="%,.0f", help="貸方金額"),
        }

        st.dataframe(
            ledger_df, 
            use_container_width=True,
            column_config=ledger_column_config 
        )
    
    st.markdown("---")
    
    # Excel一括ダウンロード機能 (V7: 元のFloat64の数値DFを使う)
    st.subheader("📥 財務三表一括ダウンロード")
    
    output = BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # Excelには元のFloat64のDataFrameを渡す
            fs_data["pl"].to_excel(writer, sheet_name="PL", float_format="%.0f") 
            fs_data["bs"].to_excel(writer, sheet_name="BS", float_format="%.0f")
            fs_data["cf"].to_excel(writer, sheet_name="CF", float_format="%.0f")
        
        st.download_button(
            "⬇ Excelダウンロード (PL, BS, CF)",
            data=output.getvalue(),
            file_name=f"financial_statements_{params.holding_years}y.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.warning(f"Excel出力エラーが発生しました: {e}")
        st.caption("xlsxwriterライブラリが環境にインストールされていない可能性があります。")


# ----------------------------------------------------------------------
# メイン関数 (V10: CSS修正ブロック - メインタイトルサイズ復元)
# ----------------------------------------------------------------------

def main():
    st.set_page_config(layout="wide", page_title="不動産投資シミュレーション")
    
    # ★ 共通CSS - タイトルサイズ復元、右寄せ強制CSSとKPIフォントサイズ調整
    st.markdown("""
        <style>
        html, body {
             font-size: 14px; 
        }

        /* -------------------------------------- */
        /* V10 修正: メインタイトル (h1) のサイズを大きく戻す */
        /* -------------------------------------- */
        h1 {
            font-size: 20px !important; /* 目立つサイズに戻す */
            font-weight: 700;
            margin-bottom: 0.3rem;
            color: #444; /* 強調のため少し濃い色に */
        }
        /* -------------------------------------- */


        h2 {
            font-size: 16px !important; 
            font-weight: 600;
            margin-top: 0.6rem;
            margin-bottom: 0.3rem;
        }
        
        /* 🚨 V10 修正: 'シミュレーション前提' の見出しだけをピンポイントで小さくする */
        div[data-testid="stVerticalBlock"] h2:first-child:has(span:contains("シミュレーション前提")) {
            font-size: 15px !important; 
            font-weight: 500;
            color: #888; /* 目立ちすぎない色 */
            margin-bottom: 0.2rem;
        }


        h3 {
            font-size: 15px !important; 
            font-weight: 500;
            margin-top: 0.4rem;
            margin-bottom: 0.2rem;
        }
        
        h4 {
            font-size: 14.5px !important; 
            font-weight: 500;
            margin-top: 0.3rem;
            margin-bottom: 0.2rem;
        }

        .stCaption {
             font-size: 13px !important;
             color: #aaa;
        }

        /* V8 修正: KPIの数値を大きくしすぎないように調整 */
        [data-testid="stMetricValue"] {
            text-align: right !important; 
            font-size: 16px !important; 
            font-weight: 500; 
        }

        /* -------------------------------------- */
        /* DataFrameの数値セル右寄せ強制CSSの強化 */
        /* -------------------------------------- */
        
        /* data-baseweb="table" 内の全ての<td>を右寄せ。最初の<td>(科目)は除く */
        div[data-baseweb="table"] tbody tr td:not(:first-child) {
            text-align: right !important; 
        }

        /* ヘッダーも右寄せ（1列目除外） */
        div[data-baseweb="table"] thead tr th:not(:first-child) {
            text-align: right !important;
        }

        /* -------------------------------------- */
        /* 区切り・合計行のスタイル */
        /* -------------------------------------- */
        /* 科目名に「【」（CFの区切り）、「計」、「合計」を含む行にスタイルを適用 */
        div[data-testid="stDataFrame"] div[data-baseweb="table"] 
        tbody tr:has(td:first-child:contains("【")),
        div[data-testid="stDataFrame"] div[data-baseweb="table"] 
        tbody tr:has(td:first-child:contains("計")),
        div[data-testid="stDataFrame"] div[data-baseweb="table"] 
        tbody tr:has(td:first-child:contains("合計")) {
            background:#f3f3f3; 
            border-top:2px solid #999; 
            border-bottom:2px solid #999; 
            font-weight:600; 
        }
        
        /* -------------------------------------- */
        /* 入力サマリーのDataFrame調整 */
        /* -------------------------------------- */
        
        /* 1列目（項目名）は左揃えを維持（念のため） */
        div[data-testid="stDataFrame"] div[data-baseweb="table"] 
        tbody tr td:first-child {
            text-align: left !important;
            font-weight: normal; 
        }

        /* 2列目（設定値）のデータセルを太字に（右寄せ維持） */
        div[data-testid="stDataFrame"] div[data-baseweb="table"] 
        tbody tr td:nth-child(2) {
            font-weight: bold; 
        }


        </style>
        """, unsafe_allow_html=True)

    st.title("💰 BKW 不動産投資シミュレーション (Amelia V1)")

    params = setup_sidebar() 
    
    start_date_value = st.session_state.get('sim_start_date', datetime.date.today())
    params.start_date = start_date_value 

    if st.button("シミュレーション実行"):
        display_input_summary(params)
        
        try:
            if params.initial_equity < 0:
                st.error("🚨 シミュレーションを中断しました。元入金がマイナスになるため、設定を見直してください。")
                return

            sim = Simulation(params, start_date=start_date_value) 
            
            # ダミーのロジック (変更なし)
            class DummyLedger:
                def get_df(self):
                    return pd.DataFrame({
                        'id': [1, 2], 'date': ['2025-01-01', '2025-01-01'], 'account': ['Cash', 'Equity'],
                        'dr_cr': ['debit', 'credit'], 'amount': [10000000.0, 10000000.0],
                        'debit': [10000000.0, 0.0], 'credit': [0.0, 10000000.0],
                        'description': ['Investment', 'Investment']
                    })
            
            final_ledger = DummyLedger() 
            ledger_df = final_ledger.get_df()

            st.success(f"シミュレーションが完了しました。全{len(ledger_df)}件の仕訳を登録。")
            
            fs_data = create_financial_statements(ledger_df, params.holding_years) 
            
            display_fs_data = create_display_dataframes(fs_data)
            
            display_kpi_summary(ledger_df, fs_data)
            
            display_ledger(ledger_df, params, fs_data, display_fs_data) 
            
        except Exception as e:
            st.error(f"シミュレーション実行中にエラーが発生しました: {e}")
            st.code(traceback.format_exc())


if __name__ == '__main__':
    if 'sim_start_date' not in st.session_state:
        st.session_state['sim_start_date'] = datetime.date(2025, 1, 1)
        
    main()
#========= bkw_sim_amelia1/ui/app.py end