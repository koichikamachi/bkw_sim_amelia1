from datetime import date
from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.ledger.ledger import Ledger
from bkw_sim_amelia1.core.ledger.journal_entry import JournalEntry
from bkw_sim_amelia1.core.engine.loan_engine import LoanEngine # LoanEngineはcore/engineにあるはず

class FinanceEngine:
    """
    以下のコードでは、月次の収益・費用、減価償却、借入返済、税金計算の仕訳を生成する
    """
    def __init__(self, params: SimulationParams, ledger: Ledger, depreciation_params: dict):
        self.params = params
        self.ledger = ledger
        
        # --- LoanEngineの初期化 (位置引数として渡す) ---
        if params.initial_loan and params.initial_loan.amount > 0 and params.initial_loan.years > 0:
            # LoanEngineが位置引数 (amount, annual_rate, years) の順序で受け取ると仮定
            self.loan_engine = LoanEngine(
                params.initial_loan.amount,          # 1番目の引数: amount
                params.initial_loan.interest_rate,   # 2番目の引数: annual_rate
                params.initial_loan.years            # 3番目の引数: years
            )
        else:
            self.loan_engine = None # ローンがない場合はNone
        # ----------------------------------------
        
        # 減価償却計算に必要な値
        self.depreciation_rate = depreciation_params["depreciation_rate"]
        
        # 建物取得原価をLedgerから取得 (初期投資の仕訳が月 index 0 で登録されているはず)
        # start_date は Simulation.py で date(2026, 1, 1) と定義していると仮定
        start_date_for_balance = date(2026, 1, 1) 
        bld_acquisition_cost = self.ledger.get_balance("建物", date=start_date_for_balance)
        
        # 建物残存簿価 
        self.bld_residual_value = 0.0 # ゼロ円償却を許容
        
        # 月次減価償却費
        annual_depreciation_base = bld_acquisition_cost - self.bld_residual_value
        self.monthly_depreciation = (annual_depreciation_base * self.depreciation_rate) / 12.0
        
    def process_month(self, month_index: int, current_date: date):
        """
        以下のコードでは、特定の月 (month_index) の全ての仕訳を生成する
        """
        # --- 1. 収益 ---
        
        # 月次家賃収入 (税抜)
        monthly_rent_ex = self.params.monthly_rent / (1 + self.params.consumption_tax_rate)
        monthly_tax_paid = self.params.monthly_rent - monthly_rent_ex # 仮受消費税
        
        # 1-1. 家賃収入 (売上 - 貸方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次家賃収入", account="売上", 
            amount=monthly_rent_ex, dr_cr="credit", category="PL", month_index=month_index
        ))
        # 1-2. 仮受消費税 (負債 - 貸方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次家賃の仮受消費税", account="仮受消費税", 
            amount=monthly_tax_paid, dr_cr="credit", category="BS", month_index=month_index
        ))
        
        # --- 2. 費用（管理費・経費） ---
        
        # 2-1. 管理委託費 (年額を12で割る)
        monthly_mgmt_fee = self.params.annual_management_fee_initial / 12.0 
        
        # 2-2. 修繕費、保険料、固定資産税、その他管理費 (全て年額を12で割る)
        monthly_repair = self.params.repair_cost_annual / 12.0
        monthly_insurance = self.params.insurance_cost_annual / 12.0
        # 固定資産税は PL 費用
        monthly_tax_fa = (self.params.fixed_asset_tax_land + self.params.fixed_asset_tax_building) / 12.0 
        monthly_other = self.params.other_management_fee_annual / 12.0
        
        # 管理委託費 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次管理委託費", account="管理費", 
            amount=monthly_mgmt_fee, dr_cr="debit", category="PL", month_index=month_index
        ))
        # 修繕費 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次修繕費", account="修繕費", 
            amount=monthly_repair, dr_cr="debit", category="PL", month_index=month_index
        ))
        # 損害保険料 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次保険料", account="損害保険料", 
            amount=monthly_insurance, dr_cr="debit", category="PL", month_index=month_index
        ))
        # 固定資産税 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次固定資産税", account="租税公課", 
            amount=monthly_tax_fa, dr_cr="debit", category="PL", month_index=month_index
        ))
        # その他管理費 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次その他管理費", account="管理費", 
            amount=monthly_other, dr_cr="debit", category="PL", month_index=month_index
        ))
        
        # --- 3. 減価償却費 ---
        
        # 3-1. 減価償却費 (PL - 借方)
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次減価償却費", account="減価償却費", 
            amount=self.monthly_depreciation, dr_cr="debit", category="PL", month_index=month_index
        ))
        # 3-2. 減価償却累計額 (BS - 貸方) ※今回は「建物」のマイナスで表現
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次減価償却累計額", account="建物", 
            amount=self.monthly_depreciation, dr_cr="credit", category="BS", month_index=month_index
        ))
        
        # --- 4. 借入金返済 ---
        
        if self.loan_engine: # ローンがある場合のみ処理
            # 月次返済額の計算 (元金、利息)
            repayment_result = self.loan_engine.calculate_monthly_payment(month_index)
            
            if repayment_result and repayment_result['total_payment'] > 0:
                principal = repayment_result['principal']
                interest = repayment_result['interest']
                cash_outflow_loan = principal + interest # 念のため再計算
                
                # 4-1. 支払利息 (PL - 借方)
                self.ledger.add_entry(JournalEntry(
                    date=current_date, description="月次支払利息", account="支払利息", 
                    amount=interest, dr_cr="debit", category="PL", month_index=month_index
                ))
                # 4-2. 元金返済 (借入金 - 借方)
                self.ledger.add_entry(JournalEntry(
                    date=current_date, description="月次元金返済", account="借入金", 
                    amount=principal, dr_cr="debit", category="BS", month_index=month_index
                ))
                
                # 4-3. 現金支出 (現金 - 貸方)
                self.ledger.add_entry(JournalEntry(
                    date=current_date, description="月次ローン支払", account="現金", 
                    amount=cash_outflow_loan, dr_cr="credit", category="BS", month_index=month_index
                ))

        # --- 5. キャッシュフローの精算 (現金収支) ---
        
        # 5-1. 現金収入 (家賃)
        cash_inflow_rent = self.params.monthly_rent
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次家賃受取 (現金)", account="現金", 
            amount=cash_inflow_rent, dr_cr="debit", category="BS", month_index=month_index
        ))
        
        # 5-2. 現金支出 (費用)
        # 管理委託費、修繕費、保険料、固定資産税、その他管理費 (今回はすべて現金支出と仮定)
        cash_outflow_expenses = monthly_mgmt_fee + monthly_repair + monthly_insurance + monthly_tax_fa + monthly_other
        self.ledger.add_entry(JournalEntry(
            date=current_date, description="月次費用支払 (現金)", account="現金", 
            amount=cash_outflow_expenses, dr_cr="credit", category="BS", month_index=month_index
        ))
        
        # TODO: 法人税等の計算と仕訳計上（年次処理）を実装する
        # TODO: 最終年の売却仕訳計上（年次処理）を実装する