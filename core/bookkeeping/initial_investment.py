# ===== core/bookkeeping/initial_investment.py =====

from datetime import date
from core.tax.tax_utils import TaxUtils
from core.bookkeeping.journal_entry import JournalEntry, make_entry_pair
from core.depreciation.unit import DepreciationUnit
from core.loan.loan_unit import LoanUnit
from core.ledger.ledger import LedgerManager

class InitialInvestmentProcessor:
    """
    初期投資ブロック
    -----------------
    ・税抜計算
    ・減価償却ユニット登録
    ・初期借入 LoanUnit 登録
    ・仕訳生成
    ・LedgerManager に積み上げ
    """

    def __init__(self, params, ledger: LedgerManager):
        self.p = params
        self.ledger = ledger

    def run(self, start_date: date):
        """
        初期投資ブロックのメイン処理
        """
        tax = TaxUtils(self.p.consumption_tax_rate, self.p.taxable_sales_ratio)

        # --------------------------
        # 1. 建物・仲介手数料の税抜計算
        # --------------------------
        bld_ex = tax.tax_exclusive(self.p.property_price_building)
        fee_ex = tax.tax_exclusive(self.p.brokerage_fee_amount_incl)

        bld_tax = tax.tax_amount(self.p.property_price_building)
        fee_tax = tax.tax_amount(self.p.brokerage_fee_amount_incl)

        bld_deductible, bld_non = tax.split_deductible(bld_tax)
        fee_deductible, fee_non = tax.split_deductible(fee_tax)

        # --------------------------
        # 2. 建物簿価の確定
        # --------------------------
        bld_boka = bld_ex + bld_non + fee_non

        # --------------------------
        # 3. 減価償却ユニット作成
        # --------------------------
        bld_unit = DepreciationUnit(
            asset_name="建物",
            acquisition_date=start_date,
            acquisition_cost=bld_boka,
            useful_life_years=self.p.building_useful_life
        )

        # --------------------------
        # 4. LoanUnit（初期借入）
        # --------------------------
        loan_unit = None
        if self.p.initial_loan:
            loan_unit = LoanUnit(
                amount=self.p.initial_loan.amount,
                annual_rate=self.p.initial_loan.interest_rate,
                years=self.p.initial_loan.years,
            )

        # --------------------------
        # 5. 初期投資仕訳
        # --------------------------
        entries = []

        # 建物
        if bld_boka > 0:
            entries.extend(
                make_entry_pair(start_date, "建物", "現金", bld_boka)
            )

        # 土地
        if self.p.property_price_land > 0:
            entries.extend(
                make_entry_pair(start_date, "土地", "現金", self.p.property_price_land)
            )

        # 仲介手数料
        if fee_ex > 0:
            entries.extend(
                make_entry_pair(start_date, "支払手数料", "現金", fee_ex)
            )

        # 仮払消費税（控除対象分）
        if bld_deductible + fee_deductible > 0:
            entries.extend(
                make_entry_pair(start_date, "仮払消費税", "現金", bld_deductible + fee_deductible)
            )

        # --------------------------
        # 6. Ledger に積み上げ
        # --------------------------
        self.ledger.add_many(entries)

        return {
            "building_unit": bld_unit,
            "loan_unit": loan_unit,
        }

# ===== end initial_investment.py =====