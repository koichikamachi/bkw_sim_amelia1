# ===============================
# core/simulation/simulation.py
# ===============================

from datetime import date
from config.params import SimulationParams
from core.ledger.ledger import LedgerManager
from core.bookkeeping.initial_entries import InitialEntryGenerator
from core.bookkeeping.monthly_entries import MonthlyEntryGenerator
from core.bookkeeping.year_end_entries import YearEndEntryGenerator


class Simulation:
    def __init__(self, params: SimulationParams, start_date: date):
        self.params = params
        self.start_date = start_date
        self.ledger = LedgerManager()

        # --------------------------------------
        # UI から渡された追加投資を整理
        # --------------------------------------
        self.additional_investments = []
        for inv in self.params.additional_investments:
            if inv.invest_amount > 0:
                self.additional_investments.append({
                    "year": inv.invest_year,
                    "amount": inv.invest_amount,
                    "life": inv.depreciation_years,
                    "loan_amount": inv.loan_amount,
                    "loan_rate": inv.loan_interest_rate,
                    "loan_years": inv.loan_years
                })

    # ============================================================
    # シミュレーション全体 run()
    # ============================================================
    def run(self):

        # ---------------------------
        # 初期投資の仕訳＋建物償却ユニット登録
        # ---------------------------
        InitialEntryGenerator(
            self.params,
            self.ledger
        ).generate(self.start_date)

        # ---------------------------
        # 月次・年次の生成器
        #   ★ここで追加投資リストを monthly に渡す
        # ---------------------------
        monthly = MonthlyEntryGenerator(
            self.params,
            self.ledger,
            self.start_date,
            additional_investments=self.additional_investments
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

            # 年次決算仕訳
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

        # 最終 Ledger を返す
        return self.ledger.get_df()

# ============= end simulation.py