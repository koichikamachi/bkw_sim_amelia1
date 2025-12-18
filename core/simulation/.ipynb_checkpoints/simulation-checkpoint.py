# =================== bkw_sim_amelia1/core/simulation/simulation.py
import pandas as pd
import numpy as np
import numpy_financial as npf
from bkw_sim_amelia1.config.params import SimulationParams
# 各専門モジュールをインポート
from bkw_sim_amelia1.core.ledger.ledger import LedgerManager
from bkw_sim_amelia1.core.bookkeeping.initial_entries import InitialEntryGenerator
from bkw_sim_amelia1.core.bookkeeping.ledger import AnnualEntryGenerator

class Simulation:
    def __init__(self, params: SimulationParams):
        """
        不動産投資シミュレーションの司令塔。
        計算エンジンで数値を出し、bookkeepingモジュールに仕訳を依頼する。
        """
        self.params = params
        self.years = params.holding_years
        # 帳簿の準備
        self.ledger_manager = LedgerManager()

    def run(self) -> pd.DataFrame:
        """
        シミュレーションのメインフローを実行し、最終的な全仕訳データを返す。
        """
        # =============================================================
        # 1. 基礎数値の計算（スケジュール作成）
        # =============================================================
        loan_schedule = self._calculate_loan_schedule()
        dep_schedule = self._calculate_depreciation_schedule()

        # =============================================================
        # 2. 開始仕訳（Year 0）の生成
        # InitialEntryGeneratorに仕訳の記録を委譲
        # =============================================================
        initial_gen = InitialEntryGenerator(self.params, self.ledger_manager)
        initial_gen.generate()

        # =============================================================
        # 3. 年度別仕訳（Year 1 ～ n）の生成
        # AnnualEntryGeneratorに各年度の仕訳記録を委譲
        # =============================================================
        annual_gen = AnnualEntryGenerator(self.params, self.ledger_manager)
        
        for y in range(1, self.years + 1):
            # その年度の計算行を抽出
            loan_row = loan_schedule.loc[y] if not loan_schedule.empty and y in loan_schedule.index else None
            dep_row = dep_schedule.loc[y] if y in dep_schedule.index else None
            
            # 仕訳を帳簿に書き込む
            annual_gen.generate_annual_entries(y, loan_row, dep_row)

        # 最終的な全仕訳リストを返す
        return self.ledger_manager.get_ledger_df()

    # =============================================================
    # 【計算エンジン】借入返済スケジュールの計算
    # =============================================================
    def _calculate_loan_schedule(self) -> pd.DataFrame:
        if not self.params.initial_loan or self.params.initial_loan.amount <= 0:
            return pd.DataFrame()
        
        p = self.params.initial_loan
        # 年間の元利均等返済額
        annual_pay = npf.pmt(p.interest_rate, p.years, -p.amount)
        
        schedule = []
        balance = p.amount
        for y in range(1, self.years + 1):
            if y <= p.years:
                interest = balance * p.interest_rate
                principal = annual_pay - interest
                balance -= principal
                schedule.append({
                    'year': y, 
                    'interest': interest, 
                    'principal': principal, 
                    'balance': max(0, balance)
                })
            else:
                schedule.append({
                    'year': y, 'interest': 0, 'principal': 0, 'balance': 0
                })
        return pd.DataFrame(schedule).set_index('year')

    # =============================================================
    # 【計算エンジン】減価償却スケジュールの計算（定額法）
    # =============================================================
    def _calculate_depreciation_schedule(self) -> pd.DataFrame:
        index = range(1, self.years + 1)
        df_dep = pd.DataFrame(0.0, index=index, columns=['expense'])
        
        # A. 初期建物の償却
        rem_life = max(1, self.params.building_useful_life - self.params.building_age)
        annual_dep = self.params.property_price_building / rem_life
        for y in index:
            if y <= rem_life:
                df_dep.loc[y, 'expense'] += annual_dep
        
        # B. 追加投資（最大5回）の償却
        for inv in self.params.additional_investments:
            if inv.invest_amount > 0:
                ann_inv_dep = inv.invest_amount / inv.depreciation_years
                for y in index:
                    if inv.invest_year <= y < inv.invest_year + inv.depreciation_years:
                        df_dep.loc[y, 'expense'] += ann_inv_dep
                        
        return df_dep

# =================== bkw_sim_amelia1/core/simulation/simulation.py end