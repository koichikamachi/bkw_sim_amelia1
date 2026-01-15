# ===== core/bookkeeping/monthly_entry.py =====

from datetime import date
from core.tax.tax_utils import TaxUtils
from core.ledger.journal_entry import make_entry_pair


class MonthlyEntryGenerator:

    def __init__(self, params, ledger, start_date):
        self.p = params
        self.ledger = ledger

        non_taxable = getattr(params, "non_taxable_proportion", 0.0)
        taxable_ratio = 1.0 - float(non_taxable)

        self.tax = TaxUtils(
            float(params.consumption_tax_rate),
            taxable_ratio
        )

        self.start_date = start_date

        # 年間集計
        self.vat_received = 0.0
        self.vat_paid = 0.0
        self.monthly_profit_total = 0.0

    # ============================================================
    # 月次処理メイン
    # ============================================================
    def generate_month(self, year: int, month: int):

        # 実日付
        current_date = date(
            self.start_date.year + (year - 1),
            month,
            1
        )

        # ------------------------------------------------------------
        # ① 家賃（非課税） → 売上
        # ------------------------------------------------------------
        rent = self.p.annual_rent_income_incl / 12

        self.ledger.add_entries(make_entry_pair(
            current_date,
            "預金",
            "売上高",
            rent
        ))
        self.monthly_profit_total += rent

        # ------------------------------------------------------------
        # ② 管理費（課税仕入）
        # ------------------------------------------------------------
        mgmt_gross = self.p.annual_management_fee_initial / 12
        mgmt_net, mgmt_tax = self.tax.split_tax(mgmt_gross)

        self.ledger.add_entries(make_entry_pair(
            current_date,
            "販売費一般管理費",
            "預金",
            mgmt_net
        ))
        self.monthly_profit_total -= mgmt_net

        mgmt_tax_deduct, mgmt_tax_nondeduct = self.tax.allocate_tax(mgmt_tax)

        if mgmt_tax_deduct > 0:
            self.ledger.add_entries(make_entry_pair(
                current_date,
                "仮払消費税",
                "預金",
                mgmt_tax_deduct
            ))
            self.vat_paid += mgmt_tax_deduct

        if mgmt_tax_nondeduct > 0:
            self.ledger.add_entries(make_entry_pair(
                current_date,
                "販売費一般管理費",
                "預金",
                mgmt_tax_nondeduct
            ))
            self.monthly_profit_total -= mgmt_tax_nondeduct

        # ------------------------------------------------------------
        # ③ 減価償却（←重要：科目名を FS に完全一致）
        # ------------------------------------------------------------
        depr_list = self.ledger.get_all_depreciation_units()

        for unit in depr_list:

            monthly_depr = unit.get_monthly_depreciation(
                current_date.year,
                current_date.month
            )
            if monthly_depr <= 0:
                continue

            # ===== 科目名を FS 側と完全一致させる =====
            if unit.asset_type == "building":
                dr = "建物減価償却費"
                cr = "建物減価償却累計額"

            elif unit.asset_type == "additional_asset":
                dr = "追加設備減価償却費"
                cr = "追加設備減価償却累計額"

            else:
                # fallback（安全策）
                dr = "減価償却費"
                cr = "減価償却累計額"

            self.ledger.add_entries(make_entry_pair(
                current_date,
                dr, cr,
                monthly_depr
            ))
            self.monthly_profit_total -= monthly_depr

        # ------------------------------------------------------------
        # ④ 借入返済
        # ------------------------------------------------------------
        loans = self.ledger.get_all_loan_units()

        for loan in loans:
            idx = (year - 1) * 12 + month
            detail = loan.calculate_monthly_payment(idx)

            if detail is None:
                continue

            principal = detail["principal"]
            interest = detail["interest"]

            if interest > 0:
                self.ledger.add_entries(make_entry_pair(
                    current_date,
                    "支払利息",
                    "預金",
                    interest
                ))
                self.monthly_profit_total -= interest

            if principal > 0:
                self.ledger.add_entries(make_entry_pair(
                    current_date,
                    "借入金",
                    "預金",
                    principal
                ))

        return True

# ===== core/bookkeeping/monthly_entry.py END