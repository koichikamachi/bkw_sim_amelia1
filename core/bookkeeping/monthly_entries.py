# ============================================================
# core/bookkeeping/monthly_entry.py  （追加投資完全対応版）
# ============================================================

from datetime import date
from core.tax.tax_utils import TaxUtils
from core.ledger.journal_entry import make_entry_pair
from core.depreciation.unit import DepreciationUnit


class MonthlyEntryGenerator:

    def __init__(self, params, ledger, start_date, additional_investments=None):
        """
        params              SimulationParams
        ledger              LedgerManager
        start_date          datetime.date
        additional_investments: List[dict]
            dict の形式:
            {
                "year": 3,
                "amount": 2200000,
                "life": 15
            }
        """

        self.p = params
        self.ledger = ledger
        self.start_date = start_date

        # Simulation.run() から渡される追加投資リスト
        self.additional_investments = additional_investments or []

        # 消費税ユーティリティ
        non_taxable = getattr(params, "non_taxable_proportion", 0.0)
        taxable_ratio = 1.0 - float(non_taxable)
        self.tax = TaxUtils(float(params.consumption_tax_rate), taxable_ratio)

        # 年間集計用
        self.vat_received = 0.0
        self.vat_paid = 0.0
        self.monthly_profit_total = 0.0

    # ============================================================
    # 月次処理メイン
    # ============================================================
    def generate_month(self, year: int, month: int):

        # 実際の年月を生成
        current_date = date(
            self.start_date.year + (year - 1),
            month,
            1
        )

        # ------------------------------------------------------------
        # ★★ A-1: 追加投資の取得仕訳を実行する（投資年の1月のみ）
        # ------------------------------------------------------------
        for inv in self.additional_investments:

            if inv["year"] == year and month == 1:

                amount = float(inv["amount"])
                life = int(inv["life"])

                # ① 取得仕訳（借方：追加設備、貸方：現金）
                self.ledger.add_entries(make_entry_pair(
                    current_date,
                    "追加設備",
                    "現金",
                    amount
                ))

                # ② 減価償却ユニット登録（取得月から償却開始）
                unit = DepreciationUnit(
                    acquisition_cost=amount,
                    useful_life_years=life,
                    start_year=current_date.year,
                    start_month=current_date.month,
                    asset_type="additional_asset"
                )
                self.ledger.register_depreciation_unit(unit)

        # ------------------------------------------------------------
        # ① 家賃収入（非課税）
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

        # 本体
        self.ledger.add_entries(make_entry_pair(
            current_date,
            "販売費一般管理費",
            "預金",
            mgmt_net
        ))
        self.monthly_profit_total -= mgmt_net

        # 消費税の処理
        mgmt_tax_deductible, mgmt_tax_nondeduct = self.tax.allocate_tax(mgmt_tax)

        if mgmt_tax_deductible > 0:
            self.ledger.add_entries(make_entry_pair(
                current_date, "仮払消費税", "預金", mgmt_tax_deductible
            ))
            self.vat_paid += mgmt_tax_deductible

        if mgmt_tax_nondeduct > 0:
            self.ledger.add_entries(make_entry_pair(
                current_date, "販売費一般管理費", "預金", mgmt_tax_nondeduct
            ))
            self.monthly_profit_total -= mgmt_tax_nondeduct

        # ------------------------------------------------------------
        # ③ 減価償却（建物＋追加設備）
        # ------------------------------------------------------------
        depr_list = self.ledger.get_all_depreciation_units()

        for unit in depr_list:

            monthly_depr = unit.get_monthly_depreciation(
                current_date.year,
                current_date.month
            )
            if monthly_depr <= 0:
                continue

            # 建物 or 追加設備で科目を切替
            if unit.asset_type == "building":
                dr = "建物減価償却費"
                cr = "建物減価償却累計額"
            else:
                dr = "追加設備減価償却費"
                cr = "追加設備減価償却累計額"

            self.ledger.add_entries(make_entry_pair(
                current_date, dr, cr, monthly_depr
            ))
            self.monthly_profit_total -= monthly_depr

        # ------------------------------------------------------------
        # ④ 借入返済
        # ------------------------------------------------------------
        loans = self.ledger.get_all_loan_units()

        for loan in loans:

            idx = (year - 1) * 12 + month
            detail = loan.calculate_monthly_payment(idx)

            if not detail:
                continue

            interest = detail["interest"]
            principal = detail["principal"]

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