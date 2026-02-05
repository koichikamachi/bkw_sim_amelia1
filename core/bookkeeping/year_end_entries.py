# ===============================================
# core/bookkeeping/year_end_entries.py
# ===============================================

from datetime import date
from core.ledger.journal_entry import make_entry_pair

class YearEndEntryGenerator:

    def __init__(self, params, ledger, start_year):
        self.p = params
        self.ledger = ledger
        self.start_year = start_year

    # ============================================================
    # 年末 VAT 相殺処理（仮受 − 仮払 → 未払消費税）
    # ============================================================
    def generate_year_end(self, year, vat_received, vat_paid, profit_total):
        
        # 年末日
        close_date = date(self.start_year + (year - 1), 12, 31)

        diff = vat_received - vat_paid

        # ======================================
        # 1) 仮受 > 仮払 → 未払消費税の発生（通常ケース）
        # ======================================
        if diff > 0:
            # 仮受消費税をゼロ化
            self.ledger.add_entries(make_entry_pair(
                close_date,
                "仮受消費税",
                "仮払消費税",
                vat_paid
            ))

            # 差額（未払消費税）
            self.ledger.add_entries(make_entry_pair(
                close_date,
                "仮受消費税",
                "未払消費税",
                diff
            ))

        # ======================================
        # 2) 仮払 > 仮受 → 未収消費税（まれだが対応）
        # ======================================
        elif diff < 0:
            amount = abs(diff)

            # 仮受消費税をゼロ化
            self.ledger.add_entries(make_entry_pair(
                close_date,
                "仮受消費税",
                "仮払消費税",
                vat_received
            ))

            # 差額（未収）
            self.ledger.add_entries(make_entry_pair(
                close_date,
                "未収消費税",
                "仮払消費税",
                amount
            ))

        # diff = 0 → 仕訳なし

        # ==================================================
        # 3) 損益振替（当期利益 → 元入金 or 繰越利益剰余金）
        # ==================================================
        # ここは既存の Profit 処理と統合可能だが最小限の実装に留める
        if profit_total != 0:
            if profit_total > 0:
                self.ledger.add_entries(make_entry_pair(
                    close_date,
                    "損益",
                    "当期利益",
                    profit_total
                ))
            else:
                self.ledger.add_entries(make_entry_pair(
                    close_date,
                    "当期利益",
                    "損益",
                    abs(profit_total)
                ))

# core/bookkeeping/year_end_entries.py end
