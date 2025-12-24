# ==================================================
# core/bookkeeping/initial_entries.py
# ==================================================

from core.ledger.journal_entry import JournalEntry
from core.ledger.ledger import LedgerManager

class InitialEntryGenerator:
    def __init__(self, params, ledger: LedgerManager):
        self.params = params
        self.ledger = ledger

    def generate(self, start_date):
        print("🔥 initial_entries.py の generate が呼ばれました")

        equity = self.params.initial_equity

        entry = JournalEntry(
            date=start_date,      # ← Simulation から受け取る
            dr_account="現金",
            cr_account="元入金",
            dr_amount=equity,
            cr_amount=equity,
            description="初期元入金"
        )

        self.ledger.add_entry(entry)