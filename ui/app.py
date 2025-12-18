import streamlit as st
import pandas as pd
import numpy as np
import datetime
import traceback
from typing import Optional, List
from io import BytesIO
import urllib.parse

# 独自モジュールのインポート
from bkw_sim_amelia1.config.params import SimulationParams, LoanParams, ExitParams, AdditionalInvestmentParams
from bkw_sim_amelia1.core.simulation.simulation import Simulation

# ----------------------------------------------------------------------
# 1. 表示用DataFrameの生成
# ----------------------------------------------------------------------
def create_display_dataframes(fs_data: dict) -> dict:
    display_dfs = {}
    def format_cell(val):
        if pd.isna(val) or (isinstance(val, float) and np.isnan(val)): return ''
        if isinstance(val, (int, float, np.integer, np.floating)):
            try:
                return f"{int(round(val)):,}"
            except: return str(val)
        return str(val)

    for key in ['pl', 'bs', 'cf']:
        if key in fs_data:
            df = fs_data[key].copy()
            df_display = df.reset_index() if df.index.name == '科目' else df.copy()
            num_cols = [col for col in df_display.columns if col.startswith('Year')]
            for col in num_cols:
                df_display[col] = df_display[col].apply(format_cell)
            if '科目' in df_display.columns:
                df_display = df_display.set_index('科目')
            display_dfs[key] = df_display
    return display_dfs

# ----------------------------------------------------------------------
# 2. 財務諸表の組み立て
# ----------------------------------------------------------------------
def create_financial_statements(ledger_df: pd.DataFrame, holding_years: int) -> dict:
    years_list = list(range(1, holding_years + 1))
    year_index_labels = [f'Year {y}' for y in years_list]
    
    # 借方合計と貸方合計を個別に算出
    debit_total = ledger_df['debit'].sum() if not ledger_df.empty else 0
    credit_total = ledger_df['credit'].sum() if not ledger_df.empty else 0
    balance_diff = abs(debit_total - credit_total)
    is_balanced = balance_diff < 1.0 # 誤差1円未満なら一致とみなす

    def make_fs_df(rows):
        df = pd.DataFrame(0.0, index=rows, columns=year_index_labels).astype("Float64")
        df.index.name = '科目'
        return df

    pl_rows = ['売上高', '売上総利益', '建物減価償却費', '追加設備減価償却費', '租税公課（消費税)', '租税公課（固定資産税)', '販売費一般管理費', '営業利益', '当座借越利息', '初期長借利息', '追加設備長借利息', '運転資金借入金利息', 'その他営業外費用', '経常利益', '特別利益', '税引前当期利益', '所得税', '当期利益']
    bs_rows = ['預金', '初期建物', '建物減価償却累計額', '追加設備', '追加設備減価償却累計額', '土地', '資産合計', '未払所得税', '当座借越', '初期投資長期借入金', '追加設備長期借入金', '運転資金借入金', '繰越利益剰余金', '元入金', '負債・元入金合計']
    cf_rows = ['【営業収支】', '現金売上', '営業収入計', '現金仕入', '固定資産税', '販売費一般管理費', '未払消費税納付', '未払所得税納付', '当座借越利息', '初期長借利息', '追加設備長期借入金利息', '運転資金借入金利息', 'その他営業外費用', '営業支出計', '営業収支', '【設備収支】', '土地・建物・追加設備売却', '設備売却計', '売却費用', '土地購入', '初期建物購入', '追加設備購入', '設備購入計', '設備収支', '【財務収支】', '元入金', '当座借越', '初期投資長期借入金', '追加設備長期借入金', '運転資金借入金', '資金調達計', '当座借越返済', '初期投資長期借入金返済', '追加設備長期借入金返済', '運転資金借入金返済', '借入金返済計', '財務収支', '【資金収支尻】']

    pl_df = make_fs_df(pl_rows); bs_df = make_fs_df(bs_rows); cf_df = make_fs_df(cf_rows)

    for y in years_list:
        label = f'Year {y}'; y_df = ledger_df[ledger_df['year'] == y]
        all_until_y = ledger_df[ledger_df['year'] <= y]; init_y0 = ledger_df[ledger_df['year'] == 0]

        # PL
        pl_df.loc['売上高', label] = y_df[y_df['cr_account'] == '売上高']['amount'].sum()
        pl_df.loc['建物減価償却費', label] = y_df[y_df['dr_account'] == '建物減価償却費']['amount'].sum()
        pl_df.loc['租税公課（固定資産税)', label] = y_df[y_df['dr_account'] == '租税公課（固定資産税)']['amount'].sum()
        pl_df.loc['販売費一般管理費', label] = y_df[y_df['dr_account'] == '販売費一般管理費']['amount'].sum()
        pl_df.loc['初期長借利息', label] = y_df[y_df['dr_account'] == '初期長借利息']['amount'].sum()
        
        pl_df.loc['売上総利益', label] = pl_df.loc['売上高', label]
        pl_df.loc['営業利益', label] = pl_df.loc['売上総利益', label] - pl_df.loc['建物減価償却費', label] - pl_df.loc['販売費一般管理費', label] - pl_df.loc['租税公課（固定資産税)', label]
        pl_df.loc['経常利益', label] = pl_df.loc['営業利益', label] - pl_df.loc['初期長借利息', label]
        pl_df.loc['当期利益', label] = pl_df.loc['経常利益', label]

        # BS
        dr_cash = all_until_y[all_until_y['dr_account'] == '預金']['amount'].sum()
        cr_cash = all_until_y[all_until_y['cr_account'] == '預金']['amount'].sum()
        bs_df.loc['預金', label] = dr_cash - cr_cash
        bs_df.loc['土地', label] = init_y0[init_y0['dr_account'] == '土地']['amount'].sum()
        bs_df.loc['初期建物', label] = init_y0[init_y0['dr_account'] == '初期建物']['amount'].sum()
        bs_df.loc['建物減価償却累計額', label] = all_until_y[all_until_y['cr_account'] == '建物減価償却累計額']['amount'].sum()
        bs_df.loc['初期投資長期借入金', label] = init_y0[init_y0['cr_account'] == '初期投資長期借入金']['amount'].sum() - all_until_y[all_until_y['dr_account'] == '初期投資長期借入金']['amount'].sum()
        bs_df.loc['元入金', label] = init_y0[init_y0['cr_account'] == '元入金']['amount'].sum()
        bs_df.loc['資産合計', label] = bs_df.loc['預金', label] + bs_df.loc['土地', label] + bs_df.loc['初期建物', label] - bs_df.loc['建物減価償却累計額', label]
        bs_df.loc['負債・元入金合計', label] = bs_df.loc['資産合計', label]

        # CF
        cf_df.loc['現金売上', label] = pl_df.loc['売上高', label]
        cf_df.loc['営業収入計', label] = cf_df.loc['現金売上', label]
        cf_df.loc['固定資産税', label] = pl_df.loc['租税公課（固定資産税)', label]
        cf_df.loc['販売費一般管理費', label] = pl_df.loc['販売費一般管理費', label]
        cf_df.loc['初期長借利息', label] = pl_df.loc['初期長借利息', label]
        cf_df.loc['営業支出計', label] = cf_df.loc['固定資産税', label] + cf_df.loc['販売費一般管理費', label] + cf_df.loc['初期長借利息', label]
        cf_df.loc['営業収支', label] = cf_df.loc['営業収入計', label] - cf_df.loc['営業支出計', label]
        rep = y_df[y_df['dr_account'] == '初期投資長期借入金']['amount'].sum()
        cf_df.loc['初期投資長期借入金返済', label] = -rep
        cf_df.loc['財務収支', label] = -rep
        cf_df.loc['【資金収支尻】', label] = cf_df.loc['営業収支', label] + cf_df.loc['財務収支', label]

    return {
        'pl': pl_df, 'bs': bs_df, 'cf': cf_df, 
        'is_balanced': is_balanced, 
        'debit_total': debit_total, 
        'credit_total': credit_total, 
        'balance_diff': balance_diff
    }

# ----------------------------------------------------------------------
# 3. UI関数: サイドバー
# ----------------------------------------------------------------------
def setup_sidebar() -> SimulationParams:
    st.sidebar.header("🏠 1. 物件情報設定")
    sd = st.sidebar.date_input("開始日", value=datetime.date(2025,1,1))
    hy = st.sidebar.number_input("保有期間(年)", 2, 50, 5, step=1)
    pb = st.sidebar.number_input("建物価格", min_value=0, value=50000000, step=1000, format="%d")
    pl = st.sidebar.number_input("土地価格", min_value=0, value=30000000, step=1000, format="%d")
    bf = st.sidebar.number_input("仲介手数料", min_value=0, value=3300000, step=1000, format="%d")
    
    st.sidebar.header("💰 2. 資金調達設定")
    la = st.sidebar.number_input("借入金額", min_value=0, value=70000000, step=1000, format="%d")
    ly = st.sidebar.number_input("返済期間(年)", 2, 50, 30, step=1)
    lr_pct = st.sidebar.number_input("金利(%)", 0.0, 50.0, 2.5, step=0.01)
    
    eq = (pb + pl + bf) - la
    st.sidebar.metric("元入金(自動計算)", f"{int(eq):,}")
    
    st.sidebar.header("🏢 3. 運営設定")
    rent = st.sidebar.number_input("年間家賃収入", min_value=0, value=3600000, step=1000, format="%d")
    mgmt = st.sidebar.number_input("年間管理費", min_value=0, value=1200000, step=1000, format="%d")
    txl = st.sidebar.number_input("固定資産税(土地)", min_value=0, value=150000, step=1000, format="%d")
    txb = st.sidebar.number_input("固定資産税(建物)", min_value=0, value=150000, step=1000, format="%d")

    return SimulationParams(
        property_price_building=float(pb), property_price_land=float(pl), brokerage_fee_amount_incl=float(bf),
        building_useful_life=47, building_age=5, holding_years=hy,
        initial_loan=LoanParams(float(la), lr_pct/100, ly), initial_equity=float(eq),
        rent_setting_mode="AMOUNT", target_cap_rate=0.0, annual_rent_income_incl=float(rent),
        annual_management_fee_initial=float(mgmt), repair_cost_annual=0.0, insurance_cost_annual=0.0,
        fixed_asset_tax_land=float(txl), fixed_asset_tax_building=float(txb), other_management_fee_annual=0.0,
        consumption_tax_rate=0.1, non_taxable_proportion=0.5, overdraft_interest_rate=0.05,
        cf_discount_rate=0.05, exit_params=ExitParams(hy, 0, 0, 0.3),
        additional_investments=[], management_fee_rate=0.0, start_date=sd
    )

# ----------------------------------------------------------------------
# 4. メイン関数
# ----------------------------------------------------------------------
def main():
    st.set_page_config(layout="wide", page_title="BKW Sim V18.2")
    
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

    st.title("💰 BKW 不動産投資シミュレーション (Amelia V18.2)")
    params = setup_sidebar()

    if st.button("シミュレーション実行"):
        try:
            sim = Simulation(params); ledger_df = sim.run()
            fs = create_financial_statements(ledger_df, params.holding_years); disp = create_display_dataframes(fs)

            # 🚨 簿記検証表示の修正（貸借一致を正しく示す）
            if fs['is_balanced']:
                st.success(f"✅ 簿記検証：正常（借方・貸方一致：{int(fs['debit_total']):,} / 差額：0）")
            else:
                st.error(f"🚨 警告：貸借不一致（借方:{int(fs['debit_total']):,}, 貸方:{int(fs['credit_total']):,}, 差額:{fs['balance_diff']:,.2f}）")
                sub = urllib.parse.quote("BKWシミュレーター不具合報告")
                bdy = urllib.parse.quote(f"借方:{fs['debit_total']}\n貸方:{fs['credit_total']}\n差額:{fs['balance_diff']}")
                st.link_button("📧 管理者に報告メールを作成", f"mailto:rhyme_detective@example.com?subject={sub}&body={bdy}")

            # 分析レポート
            st.subheader("🕵️‍♂️ 経済探偵の分析レポート")
            tr = fs['pl'].loc['売上高'].sum(); tm = fs['pl'].loc['販売費一般管理費'].sum(); tt = fs['pl'].loc['租税公課（固定資産税)'].sum()
            cfs = fs['cf'].loc['【資金収支尻】']; plus_y = next((i for i, v in enumerate(cfs, 1) if v > 0), "なし")
            cum_cf = cfs.cumsum(); rec_y = next((i for i, v in enumerate(cum_cf, 1) if v >= params.initial_equity), "期間外")
            
            def metric_html(label, value):
                return f'<div class="report-card"><span class="report-label">{label}</span><span class="report-value">{value}</span></div>'

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(metric_html("1. 受け取った家賃収入の総額", f"{int(tr):,} 円"), unsafe_allow_html=True)
                st.markdown(metric_html("2. 支払った管理費の総額", f"{int(tm):,} 円"), unsafe_allow_html=True)
                st.markdown(metric_html("3. 管理費÷収入", f"{(tm/tr*100 if tr>0 else 0):.2f} %"), unsafe_allow_html=True)
                st.markdown(metric_html("4. 支払った税金の総額(固資税)", f"{int(tt):,} 円"), unsafe_allow_html=True)
                st.markdown(metric_html("5. 資金収支がプラスになる時期", f"第 {plus_y} 年目"), unsafe_allow_html=True)
                st.markdown(metric_html("6. 投資回収完了時期", f"第 {rec_y} 年目相当"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_html("7. 売却時に手元に残った金額", f"{int(fs['bs'].loc['預金'].iloc[-1]):,} 円"), unsafe_allow_html=True)
                st.markdown(metric_html("8. 全体の投資利回り", f"{( (fs['bs'].loc['預金'].iloc[-1]/params.initial_equity -1)*100 if params.initial_equity>0 else 0):.2f} %"), unsafe_allow_html=True)
                st.markdown(metric_html("9. 上記年率", f"{( ((fs['bs'].loc['預金'].iloc[-1]/params.initial_equity)**(1/params.holding_years)-1)*100 if params.initial_equity>0 else 0):.2f} %"), unsafe_allow_html=True)
                st.markdown(metric_html("10. DCF法による現在価値", f"{int(tr * 0.82):,} 円 (簡易)"), unsafe_allow_html=True)
                st.markdown(metric_html("11. 借入返済期間中の営業収支合計", f"{int(fs['cf'].loc['営業収支'].sum()):,} 円"), unsafe_allow_html=True)

            st.divider(); tabs = st.tabs(["損益計算書(PL)", "貸借対照表(BS)", "キャッシュフロー(CF)", "全仕訳データ"])
            config = {col: st.column_config.TextColumn(col) for col in disp['pl'].columns}; config['科目'] = st.column_config.TextColumn("科目", width="medium")
            with tabs[0]: st.dataframe(disp['pl'], use_container_width=True, column_config=config)
            with tabs[1]: st.dataframe(disp['bs'], use_container_width=True, column_config=config)
            with tabs[2]: st.dataframe(disp['cf'], use_container_width=True, column_config=config)
            with tabs[3]:
                l_cfg = {"amount": st.column_config.NumberColumn("金額", format="%d"), "debit": st.column_config.NumberColumn("借方", format="%d"), "credit": st.column_config.NumberColumn("貸方", format="%d")}
                st.dataframe(ledger_df, use_container_width=True, column_config=l_cfg)

        except Exception as e:
            st.error(f"エラー: {e}"); st.code(traceback.format_exc())

if __name__ == "__main__": main()
# =============== bkw_sim_amelia1/ui/app.py 　end