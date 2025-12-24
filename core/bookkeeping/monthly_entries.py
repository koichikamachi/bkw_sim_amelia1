# ==================================
# core/bookkeeping/monthly_entries.py
# ==================================

from datetime import date
from calendar import monthrange
from core.ledger.journal_entry import JournalEntry


class MonthlyEntryGenerator:
    """
    MonthlyEntryGenerator
    ---------------------
    ・年額ベースの Params を月次に分解
    ・date は開始年固定の calendar-based
    ・月次で「現実に起きる取引」だけを仕訳化
    ・VAT（仮受・仮払）と月次損益を内部集計
    """

    def __init__(self, params, ledger_manager, start_date: date):
        self.params = params
        self.lm = ledger_manager

        # 開始年（例：2025）
        self.start_year = start_date.year

        # 年末処理用の集計バッファ（年ごとにリセットされる）
        self.vat_received = 0.0
        self.vat_paid = 0.0
        self.monthly_profit_total = 0.0

    # -------------------------------------------------
    # 月次メイン処理
    # -------------------------------------------------
    def generate_month(self, year: int, month: int):
        """
        year : シミュレーション上の年（1,2,3,...）
        month: 1〜12
        """

        actual_year = self.start_year + year - 1
        last_day = monthrange(actual_year, month)[1]
        tx_date = date(actual_year, month, last_day)

        monthly_profit = 0.0

        # 家賃収入
        monthly_profit += self._record_rent(tx_date, year, month)

        # 管理費
        monthly_profit += self._record_management_fee(tx_date, year, month)

        # 修繕費
        monthly_profit += self._record_repair_cost(tx_date, year, month)

        # 保険料
        monthly_profit += self._record_insurance(tx_date, year, month)

        # 固定資産税（月割）
        monthly_profit += self._record_property_tax(tx_date, year, month)

        # 月次利益を年次累積
        self.monthly_profit_total += monthly_profit

    # -------------------------------------------------
    # 個別取引ロジック
    # -------------------------------------------------
    def _record_rent(self, tx_date, year, month):
        annual = self.params.annual_rent_income_incl
        if annual <= 0:
            return 0.0

        amount = annual / 12

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年{month}月 家賃収入",
                dr_account="現金",
                dr_amount=amount,
                cr_account="家賃収入",
                cr_amount=amount,
            )
        )

        # 仮受消費税（非課税割合考慮）
        vat = (
            amount
            * self.params.consumption_tax_rate
            * (1 - self.params.non_taxable_proportion)
        )
        self.vat_received += vat

        return amount

    def _record_management_fee(self, tx_date, year, month):
        annual = self.params.annual_management_fee_initial
        if annual <= 0:
            return 0.0

        amount = annual / 12

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年{month}月 管理費",
                dr_account="管理費",
                dr_amount=amount,
                cr_account="現金",
                cr_amount=amount,
            )
        )

        vat = amount * self.params.consumption_tax_rate
        self.vat_paid += vat

        return -amount

    def _record_repair_cost(self, tx_date, year, month):
        annual = self.params.repair_cost_annual
        if annual <= 0:
            return 0.0

        amount = annual / 12

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年{month}月 修繕費",
                dr_account="修繕費",
                dr_amount=amount,
                cr_account="現金",
                cr_amount=amount,
            )
        )

        vat = amount * self.params.consumption_tax_rate
        self.vat_paid += vat

        return -amount

    def _record_insurance(self, tx_date, year, month):
        annual = self.params.insurance_cost_annual
        if annual <= 0:
            return 0.0

        amount = annual / 12

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年{month}月 保険料",
                dr_account="保険料",
                dr_amount=amount,
                cr_account="現金",
                cr_amount=amount,
            )
        )

        return -amount

    def _record_property_tax(self, tx_date, year, month):
        annual = (
            self.params.fixed_asset_tax_land
            + self.params.fixed_asset_tax_building
        )
        if annual <= 0:
            return 0.0

        amount = annual / 12

        self.lm.add_entry(
            JournalEntry(
                date=tx_date,
                description=f"{year}年{month}月 固定資産税",
                dr_account="固定資産税",
                dr_amount=amount,
                cr_account="現金",
                cr_amount=amount,
            )
        )

        return -amount


# ================ core/bookkeeping/monthly_entries.py end