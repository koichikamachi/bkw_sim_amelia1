# ===============================
# core/bookkeeping/annual_entries.py
# ===============================

from core.ledger.journal_entry import JournalEntry
from datetime import date
import math


class AnnualEntryGenerator:
    def __init__(self, params, ledger_manager):
        self.params = params
        self.lm = ledger_manager

    # ---------------------------------
    # 年次処理のメイン入口
    # ---------------------------------
    def generate_annual_entries(self, year: int):
        self._record_revenue(year)
        self._record_operating_costs(year)
        self._record_depreciation(year)
        self._record_loan_repayment(year)
        self._handle_overdraft(year)

    # ---------------------------------
    # 年間家賃収入
    # ---------------------------------
    def _record_revenue(self, year: int):
        amount = self.params.annual_rent_income_incl
        if amount <= 0:
            return

        entry = JournalEntry(
            date=None,
            description=f"{year}年目 家賃収入",
            dr_account="現金",
            dr_amount=amount,
            cr_account="家賃収入",
            cr_amount=amount,
        )
        self.lm.add_entry(entry)

    # ---------------------------------
    # 年間費用（簡易）
    # ---------------------------------
    def _record_operating_costs(self, year: int):
        costs = [
            ("管理費", self.params.annual_management_fee_initial),
            ("修繕費", self.params.repair_cost_annual),
            ("保険料", self.params.insurance_cost_annual),
            ("固定資産税（土地）", self.params.fixed_asset_tax_land),
            ("固定資産税（建物）", self.params.fixed_asset_tax_building),
            ("その他管理費", self.params.other_management_fee_annual),
        ]

        for name, amount in costs:
            if amount <= 0:
                continue

            entry = JournalEntry(
                date=None,
                description=f"{year}年目 {name}",
                dr_account=name,
                dr_amount=amount,
                cr_account="現金",
                cr_amount=amount,
            )
            self.lm.add_entry(entry)

    # ---------------------------------
    # 減価償却（建物のみ・定額）
    # ---------------------------------
    def _record_depreciation(self, year: int):
        bld_price = self.params.property_price_building
        life = self.params.building_useful_life

        if bld_price <= 0 or life <= 0:
            return

        annual_dep = bld_price / life

        entry = JournalEntry(
            date=None,
            description=f"{year}年目 減価償却費（建物）",
            dr_account="減価償却費",
            dr_amount=annual_dep,
            cr_account="減価償却累計額",
            cr_amount=annual_dep,
        )
        self.lm.add_entry(entry)

    # ---------------------------------
    # 借入元利返済（B-2ʼ 本体）
    # ---------------------------------
    def _record_loan_repayment(self, year: int):
        loan = self.params.initial_loan
        if loan is None:
            return

        # 返済期間を超えたら何もしない
        if year > loan.years:
            return

        P = loan.amount
        r = loan.interest_rate
        n = loan.years

        # 元利均等返済額（年1回）
        if r == 0:
            annual_payment = P / n
        else:
            annual_payment = P * r * (1 + r) ** n / ((1 + r) ** n - 1)

        interest = P * r
        principal = annual_payment - interest

        # 利息
        if interest > 0:
            self.lm.add_entry(
                JournalEntry(
                    date=None,
                    description=f"{year}年目 借入利息",
                    dr_account="支払利息",
                    dr_amount=interest,
                    cr_account="現金",
                    cr_amount=interest,
                )
            )

        # 元本返済
        if principal > 0:
            self.lm.add_entry(
                JournalEntry(
                    date=None,
                    description=f"{year}年目 元本返済",
                    dr_account="借入金",
                    dr_amount=principal,
                    cr_account="現金",
                    cr_amount=principal,
                )
            )

    # ---------------------------------
    # 当座借越（最終安全弁）
    # ---------------------------------
    def _handle_overdraft(self, year: int):
        cash_balance = self._get_cash_balance()

        if cash_balance >= 0:
            return

        overdraft = -cash_balance
        rate = self.params.overdraft_interest_rate
        interest = overdraft * rate

        # 当座借越発生
        self.lm.add_entry(
            JournalEntry(
                date=None,
                description=f"{year}年目 当座借越",
                dr_account="現金",
                dr_amount=overdraft,
                cr_account="当座借越",
                cr_amount=overdraft,
            )
        )

        # 当座借越利息
        if interest > 0:
            self.lm.add_entry(
                JournalEntry(
                    date=None,
                    description=f"{year}年目 当座借越利息",
                    dr_account="支払利息",
                    dr_amount=interest,
                    cr_account="現金",
                    cr_amount=interest,
                )
            )

    # ---------------------------------
    # 現金残高算定（Ledger走査）
    # ---------------------------------
    def _get_cash_balance(self) -> float:
        balance = 0.0
        for e in self.lm.entries:
            if e.dr_account == "現金":
                balance += e.dr_amount
            if e.cr_account == "現金":
                balance -= e.cr_amount
        return balance