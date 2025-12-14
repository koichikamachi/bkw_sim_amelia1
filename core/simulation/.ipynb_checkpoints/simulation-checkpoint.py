#==== bkw_sim_amelia1/core/simulation/simulation.py ====

from datetime import date
from dateutil.relativedelta import relativedelta 
from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.ledger.ledger import Ledger
from bkw_sim_amelia1.core.ledger.journal_entry import JournalEntry
from bkw_sim_amelia1.core.engine.finance_engine import FinanceEngine
from bkw_sim_amelia1.core.engine.loan_engine import LoanEngine 

class Simulation:
    def __init__(self, params: SimulationParams):
        self.params = params
        self.ledger = Ledger()
        self.start_date = date(2026, 1, 1)
        self.depreciation_params = self._calculate_depreciation_params() 
        
    def _calculate_depreciation_params(self) -> dict:
        """
        以下のコードでは、建物の法定耐用年数と築年数から、
        減価償却に必要な計算上の耐用年数と償却率を算出する。
        """
        L = self.params.building_useful_life # 法定耐用年数
        A = self.params.building_age         # 築年数
        
        # 1. 計算上の耐用年数 (Used Useful Life) の決定
        if A == 0:
            # 新築: 法定耐用年数 L
            U = L
        elif A < L:
            # 築浅: (法定耐用年数 - 築年数) + 築年数 * 0.2
            U = (L - A) + (A * 0.2)
        else: # A >= L (法定耐用年数経過)
            # 償却後の建物: 法定耐用年数 * 0.2
            U = L * 0.2
        
        U = max(3, round(U)) # 最低耐用年数は3年とする

        # 2. 減価償却費の計算に必要な情報を返す
        return {
            "useful_life_calculated": U,
            # (定額法を前提) 償却率 = 1 / U
            "depreciation_rate": 1.0 / U,
        }


    def _process_initial_investment(self):
        T = self.params.consumption_tax_rate             
        TR = 1.0 - self.params.non_taxable_proportion    
        MONTH_INDEX = 0 
        
        P_bld_incl = self.params.property_price_building 
        P_land = self.params.property_price_land         
        
        P_bld_ex = P_bld_incl / (1.0 + T)
        Tax_bld = P_bld_incl - P_bld_ex

        Fee_incl = self.params.brokerage_fee_amount_incl 
        Fee_ex = Fee_incl / (1.0 + T)
        Tax_fee = Fee_incl - Fee_ex
        
        Tax_paid = Tax_bld + Tax_fee 
        Tax_deductible = Tax_paid * TR
        Tax_non_deductible = Tax_paid * (1.0 - TR)

        Final_P_bld = P_bld_ex                                 
        Final_P_land = P_land + Tax_non_deductible             
        Final_Fee = Fee_ex                                      
        
        # ★ 修正箇所: 全ての JournalEntry の引数をキーワード引数で渡す ★
        self.ledger.add_entry(JournalEntry(
            date=self.start_date, description="建物取得(税抜)", account="建物", 
            amount=Final_P_bld, dr_cr="debit", category="BS", month_index=MONTH_INDEX
        ))
        
        self.ledger.add_entry(JournalEntry(
            date=self.start_date, description="土地取得(原価算入含)", account="土地", 
            amount=Final_P_land, dr_cr="debit", category="BS", month_index=MONTH_INDEX
        ))
        
        self.ledger.add_entry(JournalEntry(
            date=self.start_date, description="仲介手数料(税抜)", account="支払手数料", 
            amount=Final_Fee, dr_cr="debit", category="PL", month_index=MONTH_INDEX 
        ))
        
        self.ledger.add_entry(JournalEntry(
            date=self.start_date, description="初期仮払消費税(控除可能)", account="仮払消費税", 
            amount=Tax_deductible, dr_cr="debit", category="BS", month_index=MONTH_INDEX
        ))
        
        total_initial_cash_required = P_bld_incl + P_land + Fee_incl
        
        loan_amount = 0.0
        if self.params.initial_loan:
            loan_amount = self.params.initial_loan.amount
            self.ledger.add_entry(JournalEntry(
                date=self.start_date, description="借入金計上", account="借入金", 
                amount=loan_amount, dr_cr="credit", category="BS", month_index=MONTH_INDEX
            ))
            self.ledger.add_entry(JournalEntry(
                date=self.start_date, description="借入による現金増加", account="現金", 
                amount=loan_amount, dr_cr="debit", category="BS", month_index=MONTH_INDEX
            ))
            
        cash_movement_from_equity = total_initial_cash_required - loan_amount
        
        if cash_movement_from_equity > 0:
            self.ledger.add_entry(JournalEntry(
                date=self.start_date, description="自己資金投入", account="現金", 
                amount=cash_movement_from_equity, dr_cr="debit", category="BS", month_index=MONTH_INDEX
            ))
            self.ledger.add_entry(JournalEntry(
                date=self.start_date, description="資本金等計上", account="資本金", 
                amount=cash_movement_from_equity, dr_cr="credit", category="BS", month_index=MONTH_INDEX
            ))

        self.ledger.add_entry(JournalEntry(
            date=self.start_date, description="物件購入・初期費用支払い", account="現金", 
            amount=total_initial_cash_required, dr_cr="credit", category="BS", month_index=MONTH_INDEX
        ))


    def run(self):
        self.ledger.clear() 
        
        # 1. 初期投資の処理
        self._process_initial_investment()
        
        # 2. FinanceEngineを初期化 (減価償却情報を渡す)
        finance_engine = FinanceEngine(self.params, self.ledger, self.depreciation_params)
        
        # 3. 月次ループの期間を設定
        total_months = self.params.holding_years * 12
        current_date = self.start_date + relativedelta(months=1)
        
        for month in range(1, total_months + 1):
            finance_engine.process_month(month, current_date)
            current_date += relativedelta(months=1)

        print(f"✅ Simulation completed for {total_months} months.")
        return self.ledger
#======= 以上, core/simulation/simulation.py end ======