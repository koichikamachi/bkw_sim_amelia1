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
    """
    Simulation
    ----------
    ・初期仕訳
    ・月次仕訳
    ・年末確定処理
    """

    def __init__(self, params: SimulationParams, start_date: date):
        self.params = params
        self.start_date = start_date
        self.ledger = LedgerManager()

        # ←★★ ここにデバッグコードを入れる！！★★
        print("### LedgerManager INSTANCE =", type(self.ledger))
        print("### LedgerManager MODULE =", type(self.ledger).__module__)
        print("### LedgerManager FILE =", getattr(type(self.ledger), "__file__", "NO FILE"))
        # -------------------------------------------------------------

    def run(self):
        # 初期仕訳
        InitialEntryGenerator(
            self.params,
            self.ledger
        ).generate(self.start_date)

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

        for year in range(1, self.params.holding_years + 1):
            for month in range(1, 13):
                monthly.generate_month(year, month)

            # 年末処理
            year_end.generate_year_end(
                year,
                monthly.vat_received,
                monthly.vat_paid,
                monthly.monthly_profit_total
            )

            # 年次集計リセット
            monthly.vat_received = 0.0
            monthly.vat_paid = 0.0
            monthly.monthly_profit_total = 0.0

# ============= end simulation.py