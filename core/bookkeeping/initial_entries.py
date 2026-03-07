# ===============================================
# core/bookkeeping/initial_entries.py
# 仕様書 第5章 InitialEntryGenerator 準拠版
# ===============================================

from datetime import date
from core.tax.tax_splitter import split_vat
from core.tax.broker_fee_allocator import allocate_broker_fee
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanUnit
from core.ledger.journal_entry import make_entry_pair


class InitialEntryGenerator:
    """
    仕様書 第5章 InitialEntryGenerator

    取得フェーズの仕訳生成と、償却ユニット・ローンユニットの登録を担当する。

    処理内容（仕様書5.3節）：
        1. 建物（税込 → 税抜 + 仮払消費税 + 控除不能VAT算入）
        2. 土地（非課税）
        3. 仲介手数料（土地・建物に按分）
        4. 建物の減価償却ユニット登録
        5. 元入金
        6. 初期借入金（長期借入金）
        ※ 追加設備は monthly_entries.py が投資年月に処理する（二重登録防止）
    """

    def __init__(self, params, ledger):
        self.p = params
        self.ledger = ledger
        self.vat_rate          = float(params.consumption_tax_rate)
        self.non_taxable_ratio = float(params.non_taxable_proportion)
        self.taxable_ratio     = 1.0 - self.non_taxable_ratio

    # --------------------------------------------------------
    # 初期投資仕訳生成（仕様書5.4節 generate(start_date)）
    # --------------------------------------------------------
    def generate(self, start_date: date) -> bool:

        p  = self.p
        d0 = start_date

        # ======================================================
        # 1) 建物（税込 → 税抜 + 仮払消費税）
        # ======================================================
        bld_gross = float(str(p.property_price_building).replace(",", ""))

        b = split_vat(
            gross_amount=bld_gross,
            vat_rate=self.vat_rate,
            non_taxable_ratio=self.non_taxable_ratio,
        )
        b_net    = b["tax_base"]
        b_vat_d  = b["vat_deductible"]     # 控除可能 → 仮払消費税
        b_vat_nd = b["vat_nondeductible"]  # 控除不能 → 建物原価に算入

        if b_net > 0:
            self.ledger.add_entries(make_entry_pair(d0, "建物", "預金", b_net))
        if b_vat_d > 0:
            self.ledger.add_entries(make_entry_pair(d0, "仮払消費税", "預金", b_vat_d))
        if b_vat_nd > 0:
            self.ledger.add_entries(make_entry_pair(d0, "建物", "預金", b_vat_nd))
            b_net += b_vat_nd  # 償却対象原価に加算

        # ======================================================
        # 2) 土地（非課税）
        # ======================================================
        land = float(str(p.property_price_land).replace(",", ""))
        if land > 0:
            self.ledger.add_entries(make_entry_pair(d0, "土地", "預金", land))

        # ======================================================
        # 3) 仲介手数料（税込 → 土地・建物に按分）
        # ======================================================
        broker_gross = float(str(p.brokerage_fee_amount_incl).replace(",", ""))
        if broker_gross > 0:
            alloc = allocate_broker_fee(
                gross_broker_fee=broker_gross,
                land_net=land,
                building_net=b_net,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            land_add = alloc["land_cost_addition"]
            bld_add  = alloc["building_cost_addition"]
            vat_d    = alloc["vat_deductible"]
            vat_nd   = alloc["vat_nondeductible"]

            if land_add > 0:
                self.ledger.add_entries(make_entry_pair(d0, "土地",   "預金", land_add))
            if bld_add > 0:
                self.ledger.add_entries(make_entry_pair(d0, "建物",   "預金", bld_add))
                b_net += bld_add
            if vat_d > 0:
                self.ledger.add_entries(make_entry_pair(d0, "仮払消費税", "預金", vat_d))
            if vat_nd > 0:
                self.ledger.add_entries(make_entry_pair(d0, "建物",   "預金", vat_nd))
                b_net += vat_nd

        # ======================================================
        # 4) 建物の減価償却ユニット登録（仕様書5.8節）
        # ======================================================
        if b_net > 0:
            unit = DepreciationUnit(
                acquisition_cost=b_net,
                useful_life_years=int(p.building_useful_life),
                start_year=d0.year,
                start_month=d0.month,
                asset_type="building",
            )
            self.ledger.register_depreciation_unit(unit)

        # ======================================================
        # 5) 元入金（仕様書5.5節）
        # ======================================================
        if p.initial_equity > 0:
            self.ledger.add_entries(make_entry_pair(
                d0, "預金", "元入金", p.initial_equity
            ))

        # ======================================================
        # 6) 初期借入金（長期借入金）
        #    科目名：仕様書CoA「長期借入金」に統一
        # ======================================================
        if p.initial_loan and p.initial_loan.amount > 0:
            loan = LoanUnit(
                amount=p.initial_loan.amount,
                annual_rate=p.initial_loan.interest_rate,
                years=p.initial_loan.years,
                repayment_method=getattr(p.initial_loan, "repayment_method", "annuity"),
                loan_type="initial",
                start_sim_month=1,
            )
            self.ledger.register_loan_unit(loan)

            self.ledger.add_entries(make_entry_pair(
                d0, "預金", "長期借入金", p.initial_loan.amount
            ))

        # ======================================================
        # ※ 追加設備の仕訳・DepreciationUnit登録は
        #    monthly_entries.py が投資年月（各年1月）に処理する。
        #    ここで処理すると二重登録になるため記述しない。
        # ======================================================

        return True

# ===============================================
# core/bookkeeping/initial_entries.py end
# ===============================================