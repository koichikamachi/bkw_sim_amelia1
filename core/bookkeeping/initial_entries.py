# ===============================================
# core/bookkeeping/initial_entries.py（修正版）
# ===============================================

from datetime import date
from core.tax.tax_splitter import split_vat
from core.tax.broker_fee_allocator import allocate_broker_fee
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanEngine
from core.ledger.journal_entry import make_entry_pair


class InitialEntryGenerator:

    def __init__(self, params, ledger):
        self.p = params
        self.ledger = ledger

        self.vat_rate = float(params.consumption_tax_rate)
        self.non_taxable_ratio = float(params.non_taxable_proportion)

    # --------------------------------------------------------
    # 初期投資仕訳生成
    # --------------------------------------------------------
    def generate(self, start_date: date):

        p = self.p
        date0 = start_date

        # ======================================================
        # 1) 建物（税込）→ split → 税抜本体 + VAT
        # ======================================================
        bld_price_incl = float(str(p.property_price_building).replace(",", ""))

        bld_split = split_vat(
            gross_amount=bld_price_incl,
            vat_rate=self.vat_rate,
            non_taxable_ratio=self.non_taxable_ratio,
        )

        building_net = bld_split["tax_base"]
        building_vat_d = bld_split["vat_deductible"]
        building_vat_nd = bld_split["vat_nondeductible"]

        # ★ 「建物」→「建物」に統一（帳簿科目）ことを訂正
        if building_net > 0:
            self.ledger.add_entries(make_entry_pair(
                date=date0,
                debit_account="建物",
                credit_account="現金",
                amount=building_net
            ))

        if building_vat_d > 0:
            self.ledger.add_entries(make_entry_pair(
                date=date0,
                debit_account="仮払消費税",
                credit_account="現金",
                amount=building_vat_d
            ))

        if building_vat_nd > 0:
            self.ledger.add_entries(make_entry_pair(
                date=date0,
                debit_account="建物",
                credit_account="現金",
                amount=building_vat_nd
            ))
            building_net += building_vat_nd

        # ======================================================
        # 2) 土地（非課税）
        # ======================================================
        land_price = float(str(p.property_price_land).replace(",", ""))

        if land_price > 0:
            self.ledger.add_entries(make_entry_pair(
                date=date0,
                debit_account="土地",
                credit_account="現金",
                amount=land_price
            ))

        # ======================================================
        # 3) 仲介手数料（税込）→ 土地・建物へ按分
        # ======================================================
        broker_incl = float(str(p.brokerage_fee_amount_incl).replace(",", ""))

        if broker_incl > 0:

            alloc = allocate_broker_fee(
                gross_broker_fee=broker_incl,
                land_net=land_price,
                building_net=building_net,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )

            land_add = alloc["land_cost_addition"]
            bld_add = alloc["building_cost_addition"]
            vat_d = alloc["vat_deductible"]
            vat_nd = alloc["vat_nondeductible"]

            # 土地加算
            if land_add > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=date0,
                    debit_account="土地",
                    credit_account="現金",
                    amount=land_add
                ))

            # 建物加算（帳簿科目は「建物」に統一）を訂正
            if bld_add > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=date0,
                    debit_account="建物",
                    credit_account="現金",
                    amount=bld_add
                ))
                building_net += bld_add

            # 控除可能 VAT（課税売上対応分）
            if vat_d > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=date0,
                    debit_account="仮払消費税",
                    credit_account="現金",
                    amount=vat_d
                ))

            # 控除不能 VAT → 建物原価算入
            if vat_nd > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=date0,
                    debit_account="建物",
                    credit_account="現金",
                    amount=vat_nd
                ))
                building_net += vat_nd

        # ======================================================
        # 4) 減価償却ユニット登録（建物）
        #     ※ asset_type は "building" 固定（DepreciationUnit の仕様）
        # ======================================================
        if building_net > 0:
            unit = DepreciationUnit(
                acquisition_cost=building_net,
                useful_life_years=int(p.building_useful_life),
                start_year=date0.year,
                start_month=date0.month,
                asset_type="building"   # ← 正しい指定
            )
            self.ledger.register_depreciation_unit(unit)

        # ======================================================
        # 5) 初期借入
        # ======================================================
        if p.initial_loan:

            loan_amt = p.initial_loan.amount
            loan_rate = p.initial_loan.interest_rate
            loan_years = p.initial_loan.years

            if loan_amt > 0:
                loan = LoanEngine(
                    amount=loan_amt,
                    annual_rate=loan_rate,
                    years=loan_years
                )
                self.ledger.register_loan_unit(loan)

                self.ledger.add_entries(make_entry_pair(
                    date=date0,
                    debit_account="現金",
                    credit_account="借入金",
                    amount=loan_amt
                ))

        # ======================================================
        # 6) 元入金
        # ======================================================
        if p.initial_equity > 0:
            self.ledger.add_entries(make_entry_pair(
                date=date0,
                debit_account="現金",
                credit_account="元入金",
                amount=p.initial_equity
            ))

        return True

# END