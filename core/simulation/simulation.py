# ===============================
# core/simulation/simulation.py
# ===============================
from datetime import date
from config.params import SimulationParams
from core.ledger.ledger import LedgerManager
from core.bookkeeping.initial_entries import InitialEntryGenerator
from core.bookkeeping.monthly_entries import MonthlyEntryGenerator
from core.bookkeeping.year_end_entries import YearEndEntryGenerator
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanEngine
from core.ledger.journal_entry import make_entry_pair


class Simulation:
    def __init__(self, params: SimulationParams, start_date: date):
        self.params = params
        self.start_date = start_date
        self.ledger = LedgerManager()

    # ============================================================
    # 追加投資の登録
    # ============================================================
    def _generate_additional_investments(self):
        print("DEBUG: entering _generate_additional_investments, count =",
              len(self.params.additional_investments))

        for inv in self.params.additional_investments:

            # 追加投資が発生する1月1日
            invest_date = date(
                self.start_date.year + (inv.invest_year - 1),
                1,
                1
            )

            # ---------------------------
            # 償却ユニット登録
            # ---------------------------
            unit = DepreciationUnit(
                acquisition_cost=inv.invest_amount,
                useful_life_years=inv.depreciation_years,
                start_year=invest_date.year,
                start_month=invest_date.month,
                asset_type="additional_asset"
            )
            self.ledger.register_depreciation_unit(unit)

            # ---------------------------
            # 追加設備の仕訳
            # ---------------------------
            self.ledger.add_entries(make_entry_pair(
                invest_date,
                "追加設備",
                "現金",
                inv.invest_amount
            ))

            # ---------------------------
            # 借入がある場合
            # ---------------------------
            if inv.loan_amount > 0:
                loan = LoanEngine(
                    amount=inv.loan_amount,
                    annual_rate=inv.loan_interest_rate,
                    years=inv.loan_years
                )
                self.ledger.register_loan_unit(loan)

                self.ledger.add_entries(make_entry_pair(
                    invest_date,
                    "現金",
                    "追加設備長期借入金",
                    inv.loan_amount
                ))

    # ============================================================
    # シミュレーション全体 run()
    # ============================================================
    def run(self):
        print("DEBUG: additional_investments received in Simulation.run():")
        print(self.params.additional_investments)

        # ---------------------------
        # 初期投資の仕訳＋建物償却ユニットの登録
        # ---------------------------
        InitialEntryGenerator(
            self.params,
            self.ledger
        ).generate(self.start_date)

        # ---------------------------
        # 追加投資の登録（償却ユニット＋仕訳）
        # ---------------------------
        self._generate_additional_investments()

        # ---------------------------
        # 月次・年次の生成器
        # ---------------------------
        monthly = MonthlyEntryGenerator(
            self.params,
            self.ledger,
            self.start_date
        )
        year_end = YearEndEntryGenerator(
            self.params,
            self.ledger,
            self.start_date.year
        )

        # ---------------------------
        # メインループ
        # ---------------------------
        for year in range(1, self.params.holding_years + 1):

            for month in range(1, 12 + 1):
                monthly.generate_month(year, month)

            year_end.generate_year_end(
                year,
                monthly.vat_received,
                monthly.vat_paid,
                monthly.monthly_profit_total
            )

            # Reset annual accumulators
            monthly.vat_received = 0.0
            monthly.vat_paid = 0.0
            monthly.monthly_profit_total = 0.0

# ============= end simulation.py