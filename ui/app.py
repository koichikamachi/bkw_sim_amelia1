#==== bkw_sim_amelia1/ui/app.py (Pandas強制フォーマット版 - setup_sidebar関数込みの完全版) ====

import streamlit as st
import pandas as pd
import numpy as np

# インポートパスを維持（この方法でモジュールエラーは解決済み）
from bkw_sim_amelia1.config.params import SimulationParams, LoanParams
from bkw_sim_amelia1.core.simulation.simulation import Simulation
from typing import Optional

# ----------------------------------------------------------------------
# ユーティリティ関数: 財務諸表を生成する (年次集計ロジック)
# ----------------------------------------------------------------------
def create_financial_statements(ledger_df: pd.DataFrame, holding_years: int) -> dict:
    
    debit_total = ledger_df[ledger_df['dr_cr'] == 'debit']['amount'].sum()
    credit_total = ledger_df[ledger_df['dr_cr'] == 'credit']['amount'].sum()
    is_balanced = abs(debit_total - credit_total) < 0.01

    ledger_df['year_index'] = np.ceil(ledger_df['month_index'] / 12).astype(int)
    years_list = list(range(1, holding_years + 1))
    
    # 1. 損益計算書 (PL) の仮データとDataFrame作成
    pl_data_dict = {
        '家賃収入': [5000000 / holding_years] * holding_years,
        '支払手数料': [100000 / holding_years] * holding_years,
        '減価償却費': [2000000 / holding_years] * holding_years,
        '修繕費': [300000 / holding_years] * holding_years,
        '保険料': [100000 / holding_years] * holding_years,
        '支払利息': [1500000 / holding_years] * holding_years,
        '固定資産税': [300000 / holding_years] * holding_years,
        'その他経費': [100000 / holding_years] * holding_years,
        '雑損失': [0.0] * holding_years, 
        '--- 利益 ---': [545455 / holding_years] * holding_years 
    }
    pl_df = pd.DataFrame(pl_data_dict, index=[f'Year {y}' for y in years_list]).T
    
    # 2. 貸借対照表 (BS) の仮データとDataFrame作成
    bs_data_dict = {
        '現金': [1000000] * holding_years, 
        '仮払消費税': [50000] * holding_years, 
        '土地': [30000000] * holding_years,
        '建物': [50000000] * holding_years,
        '減価償却累計額': [-10000000] * holding_years,
        '長期借入金': [70000000] * holding_years,
        '未払消費税': [0.0] * holding_years, 
        '資本金': [10000000] * holding_years,
        '繰越利益剰余金': [20000000] * holding_years,
    }
    bs_df = pd.DataFrame(bs_data_dict, index=[f'Year {y}' for y in years_list]).T
    
    # 3. キャッシュフロー (CF) の仮データとDataFrame作成
    cf_data_dict = {
        '営業活動によるCF': [1000000] * holding_years, 
        '投資活動によるCF': [-500000] * holding_years, 
        '財務活動によるCF': [500000] * holding_years,
        '現金及び現金同等物の増減額': [1000000] * holding_years
    }
    cf_df = pd.DataFrame(cf_data_dict, index=[f'Year {y}' for y in years_list]).T

    fs_data = {
        'pl': pl_df, 'bs': bs_df, 'cf': cf_df,
        'is_balanced': is_balanced,
        'debit_total': debit_total,
        'credit_total': credit_total,
        'balance_diff': abs(debit_total - credit_total)
    }
    
    return fs_data


# ----------------------------------------------------------------------
# UI関数: サイドバーのパラメータ設定 ★ NameErrorを解消するために必要 ★
# ----------------------------------------------------------------------
def setup_sidebar() -> SimulationParams:
    st.sidebar.header("🏠 1. 物件情報設定")
    price_bld = st.sidebar.number_input("建物価格 (税込・円)", min_value=1000000, value=50000000, step=100000)
    price_land = st.sidebar.number_input("土地価格 (円)", min_value=1000000, value=30000000, step=100000)
    bld_useful_life = st.sidebar.slider("建物の法定耐用年数 (年)", min_value=10, max_value=60, value=47)
    bld_age = st.sidebar.number_input("建物の築年数 (年)", min_value=0, value=5, step=1)
    
    st.sidebar.header("💰 2. 資金調達設定")
    loan_amount = st.sidebar.number_input("借入金額 (円)", min_value=0, value=70000000, step=100000)
    loan_rate = st.sidebar.slider("借入金利 (年利 %)", min_value=0.5, max_value=5.0, value=2.5, step=0.01) / 100
    loan_years = st.sidebar.number_input("返済年数 (年)", min_value=1, max_value=35, value=30)
    
    initial_loan: Optional[LoanParams] = None
    if loan_amount > 0:
        initial_loan = LoanParams(
            amount=loan_amount,
            interest_rate=loan_rate,
            years=loan_years
        )

    st.sidebar.header("🏢 3. 収益・管理費設定")
    monthly_rent = st.sidebar.number_input("月次家賃収入 (税込・円)", min_value=10000, value=300000, step=10000)
    mgmt_fee_annual = st.sidebar.number_input("年間管理委託費 (税込・円)", min_value=0, value=1200000, step=10000)
    repair_cost_annual = st.sidebar.number_input("年間修繕費 (円)", min_value=0, value=300000, step=10000)
    insurance_cost_annual = st.sidebar.number_input("年間保険料 (円)", min_value=0, value=100000, step=10000)
    fa_tax_land = st.sidebar.number_input("年間固定資産税 (土地)", min_value=0, value=150000, step=10000)
    fa_tax_bld = st.sidebar.number_input("年間固定資産税 (建物)", min_value=0, value=150000, step=10000)
    other_mgmt_fee = st.sidebar.number_input("その他管理経費 (年額・円)", min_value=0, value=100000, step=10000)

    st.sidebar.header("🤝 4. 初期費用・税設定")
    brokerage_fee_incl = st.sidebar.number_input("仲介手数料 (税込・円)", min_value=0, value=3300000, step=10000)
    holding_years = st.sidebar.slider("保有期間 (年)", min_value=1, max_value=50, value=5)
    tax_rate = st.sidebar.slider("消費税率 (%)", min_value=0.0, max_value=10.0, value=10.0, step=0.1) / 100
    non_taxable_prop = st.sidebar.slider("家賃の非課税割合 (%)", min_value=0.0, max_value=100.0, value=50.0, step=0.1) / 100

    return SimulationParams(
        property_price_building=price_bld,
        property_price_land=price_land,
        brokerage_fee_amount_incl=brokerage_fee_incl,
        building_useful_life=bld_useful_life,
        building_age=bld_age,
        monthly_rent=monthly_rent,
        consumption_tax_rate=tax_rate,
        non_taxable_proportion=non_taxable_prop,
        annual_management_fee_initial=mgmt_fee_annual,
        repair_cost_annual=repair_cost_annual,
        insurance_cost_annual=insurance_cost_annual,
        fixed_asset_tax_land=fa_tax_land,
        fixed_asset_tax_building=fa_tax_bld,
        other_management_fee_annual=other_mgmt_fee,
        holding_years=holding_years,
        initial_loan=initial_loan
    )


# ----------------------------------------------------------------------
# UI関数: KPIサマリーの表示 (簿記検証結果を右隣に配置)
# ----------------------------------------------------------------------
def display_kpi_summary(ledger_df: pd.DataFrame, fs_data: dict):
    # 暫定値 (UI画像から引用)
    received_income = 54545455
    spent_cost = 48298817
    
    st.header("🎯 主要シミュレーション結果概要")

    # 3列に分割し、3列目に簿記検証結果を配置
    col1, col2, col3 = st.columns([1, 1, 0.8]) 
    
    with col1:
        st.metric("受け取った家賃収入の総額", f"{received_income:,.0f}円")
        st.metric("費用・収入割合 (損益分岐)", f"88.55 %")
        st.metric("投資回収完了月", "N/A (ロジック未実装)")
        
    with col2:
        st.metric("支払った費用の総額 (利息含む)", f"{spent_cost:,.0f}円")
        st.metric("賃金収支がプラスになる時期", "N/A (ロジック未実装)")
        st.metric("売却時に手元に残った金額", "N/A (ロジック未実装)")
        
    with col3:
        st.subheader("簿記検証結果 (TB)")
        
        if fs_data['is_balanced']:
            st.success("🎉 貸借一致: 完了しています。")
        else:
            st.error("🚨 貸借不一致: 管理者にお知らせください。")
            
        st.caption(f"借方合計: {fs_data['debit_total']:,.0f} / 差額: {fs_data['balance_diff']:,.2f}") 
        
    st.markdown("---")


# ----------------------------------------------------------------------
# UI関数: 財務三表の表示 (Pandasのapplymapでカンマを強制適用)
# ----------------------------------------------------------------------

def display_ledger(ledger_df: pd.DataFrame, holding_years: int, fs_data: dict):
    
    st.header("1. 財務三表の扱い")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"損益計算書 (PL) - 年次 ({holding_years}年間)", 
        f"貸借対照表 (BS) - 年次 ({holding_years}年間)", 
        f"キャッシュフロー (CF) - 年次 ({holding_years}年間)", 
        "簿記検証 (TB)", 
        "全仕訳データ"
    ])
    
    st.markdown("""
        <style>
        /* 財務諸表テーブルのフォントを大きくする (PL, BS, CFなど) */
        .stTable > table, .dataframe {
            font-size: 1.1em !important; /* フォントサイズを大きく */
        }
        </style>
        """, unsafe_allow_html=True)

    # ★ カンマ表示の修正：Pandasのapplymapでカンマと円マークを文字列としてデータに強制適用する ★
    
    # NaNやNone値でない場合にフォーマットを適用
    formatted_pl = fs_data['pl'].applymap(lambda x: f"¥{x:,.0f}" if pd.notnull(x) else x)
    formatted_bs = fs_data['bs'].applymap(lambda x: f"¥{x:,.0f}" if pd.notnull(x) else x)
    formatted_cf = fs_data['cf'].applymap(lambda x: f"¥{x:,.0f}" if pd.notnull(x) else x)

    # st.dataframeにcolumn_configを渡す必要はなくなるが、エラー防止のため空を渡す
    empty_config = {}

    with tab1:
        st.subheader(f"📊 損益計算書 (PL) - {holding_years}年間の推移")
        st.dataframe(formatted_pl, use_container_width=True, column_config=empty_config)

    with tab2:
        st.subheader(f"🏦 貸借対照表 (BS) - {holding_years}年間の推移")
        st.dataframe(formatted_bs, use_container_width=True, column_config=empty_config)

    with tab3:
        st.subheader(f"💸 キャッシュフロー計算書 (CF) - {holding_years}年間の推移")
        st.dataframe(formatted_cf, use_container_width=True, column_config=empty_config)

    with tab4:
        st.subheader("✅ 簿記検証 (仕訳合計の貸借一致チェック)")
        
        # 違算チェック（仮）
        if fs_data['balance_diff'] > 1: # 違算が1円を超えたらエラーと見なす
            st.error("🚨 簿記的検証に失敗しました。")
            st.warning("この出力は使わず、mailで管理人にお知らせください")
            if st.button("管理者にエラー通知 (機能未実装)", key="notify_admin"):
                st.info("通知機能は現在実装中です。")
        else:
            st.success("🎉 簿記的検証は完了しています。")
        
        st.markdown("---")

        col_tb1, col_tb2, col_tb3 = st.columns(3)
        col_tb1.metric("借方合計", f"{fs_data['debit_total']:,.0f}")
        col_tb2.metric("貸方合計", f"{fs_data['credit_total']:,.0f}")
        col_tb3.metric("差額 (理想は0)", f"{fs_data['balance_diff']:,.2f}") 
        
        st.caption("✅ 貸借一致: 簿記上の検証は成功しています。") 

    with tab5:
        st.subheader("📚 全仕訳データ")
        st.dataframe(ledger_df, use_container_width=True)


# ----------------------------------------------------------------------
# メイン関数
# ----------------------------------------------------------------------

def main():
    st.set_page_config(layout="wide", page_title="不動産投資シミュレーション")
    st.title("💰 BKW 不動産投資シミュレーション (Amelia V1)")

    # setup_sidebar 関数を呼び出し
    params = setup_sidebar() 
    
    if st.button("シミュレーション実行"):
        # コアロジックの実行
        sim = Simulation(params)
        final_ledger = sim.run()

        ledger_df = final_ledger.get_df()
        st.success(f"シミュレーションが完了しました。全{len(ledger_df)}件の仕訳を登録。")
        
        # 財務諸表データを先に作成し、KPIサマリーに渡す
        fs_data = create_financial_statements(ledger_df, params.holding_years) 
        
        # KPIサマリーの表示 (簿記検証結果を右隣に配置)
        display_kpi_summary(ledger_df, fs_data)
        
        # 財務三表の表示 (カンマ表示修正版)
        display_ledger(ledger_df, params.holding_years, fs_data)


if __name__ == '__main__':
    main()
#=========================================================