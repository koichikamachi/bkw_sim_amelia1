# ===============================
# core/bookkeeping/year_end_entries.py
# ===============================

from datetime import date
# from core.ledger.journal_entry import JournalEntry
from core.ledger.journal_entry import JournalEntry, make_entry_pair

class YearEndEntryGenerator:
    """
    年末処理（12月）
    ----------------
    ・消費税確定
    ・当期所得税確定
    """

    def __init__(self, params, ledger_manager, start_year: int):
        self.params = params
        self.lm = ledger_manager
        self.start_year = start_year

    def generate_year_end(self, year: int, vat_received, vat_paid, profit_total):
        tx_date = date(self.start_year + year - 1, 12, 31)

        self._finalize_vat(tx_date, vat_received, vat_paid, year)
        self._finalize_income_tax(tx_date, profit_total, year)

    # ---------------------------------
    # 消費税確定
    # ---------------------------------
    def _finalize_vat(self, tx_date, vat_received, vat_paid, year):
        diff = vat_received - vat_paid
        if diff <= 0:
            return

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年 消費税確定",
                dr_account="租税公課",
                dr_amount=diff,
                cr_account="未払消費税",
                cr_amount=diff,
            )
        )

    # ---------------------------------
    # 当期所得税確定
    # ---------------------------------
    def _finalize_income_tax(self, tx_date, profit, year):
        if profit <= 0:
            return

        tax = profit * self.params.exit_params.income_tax_rate

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年 当期所得税",
                dr_account="当期所得税",
                dr_amount=tax,
                cr_account="未払所得税",
                cr_amount=tax,
            )
        )


# ============== core/bookkeeping/year_end_entries.py end