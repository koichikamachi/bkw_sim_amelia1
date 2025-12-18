from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.ledger.ledger import LedgerManager

class AnnualEntryGenerator:
    def __init__(self, params: SimulationParams, ledger_manager: LedgerManager):
        """
        毎年の運営フェーズ（Year 1 ～ n）の仕訳を生成する専門クラス。
        bkw_sim_amelia1/core/bookkeeping/ledger.py に配置。
        """
        self.params = params
        self.lm = ledger_manager

    # =============================================================
    # 特定年度の運営仕訳を一括生成
    # =============================================================
    def generate_annual_entries(self, year: int, loan_row, dep_row):
        """
        year: 対象年度
        loan_row: simulation.pyで計算されたその年の借入返済データ
        dep_row: simulation.pyで計算されたその年の減価償却データ
        """
        self._record_revenue(year)
        self._record_expenses(year)
        self._record_depreciation(year, dep_row)
        self._record_loan_service(year, loan_row)

    # =============================================================
    # 1. 収益の記録（家賃収入）
    # =============================================================
    def _record_revenue(self, year: int):
        # 借方：預金 / 貸方：売上高（家賃収入）
        self.lm.add_entry(
            year, "預金", "売上高", 
            self.params.annual_rent_income_incl, 
            "家賃収入計上"
        )

    # =============================================================
    # 2. 現金支出費用の記録（管理費、修繕費、固定資産税等）
    # =============================================================
    def _record_expenses(self, year: int):
        # UIから入力された各経費を合算
        total_cash_expenses = (
            self.params.annual_management_fee_initial +
            self.params.repair_cost_annual +
            self.params.insurance_cost_annual +
            self.params.fixed_asset_tax_land +
            self.params.fixed_asset_tax_building +
            self.params.other_management_fee_annual
        )
        
        # 借方：販売費一般管理費 / 貸方：預金
        self.lm.add_entry(
            year, "販売費一般管理費", "預金", 
            total_cash_expenses, 
            "運営諸経費支払"
        )

    # =============================================================
    # 3. 非現金支出費用の記録（減価償却費）
    # =============================================================
    def _record_depreciation(self, year: int, dep_row):
        if dep_row is not None and dep_row['expense'] > 0:
            # 借方：建物減価償却費 / 貸方：建物減価償却累計額
            self.lm.add_entry(
                year, "建物減価償却費", "建物減価償却累計額", 
                dep_row['expense'], 
                "建物減価償却計上"
            )

    # =============================================================
    # 4. 財務活動の記録（借入金の利息支払と元金返済）
    # =============================================================
    def _record_loan_service(self, year: int, loan_row):
        if loan_row is not None:
            # 利息の支払（借方：初期長借利息 / 貸方：預金）
            if loan_row['interest'] > 0:
                self.lm.add_entry(
                    year, "初期長借利息", "預金", 
                    loan_row['interest'], 
                    "初期借入金利息支払"
                )
            
            # 元金の返済（借方：初期投資長期借入金 / 貸方：預金）
            if loan_row['principal'] > 0:
                self.lm.add_entry(
                    year, "初期投資長期借入金", "預金", 
                    loan_row['principal'], 
                    "初期借入金元金返済"
                )