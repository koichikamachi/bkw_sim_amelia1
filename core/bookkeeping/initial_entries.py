# ===============================================
# core/bookkeeping/initial_entries.py（正統・完全版）
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
        self.taxable_ratio = 1 - self.non_taxable_ratio


    # --------------------------------------------------------
    # 初期投資仕訳生成
    # --------------------------------------------------------
    def generate(self, start_date: date):

        p = self.p
        d0 = start_date

        # ======================================================
        # 1) 建物（税込）→ 税抜本体＋VAT → 非課税割合分を建物に算入
        # ======================================================
        bld_gross = float(str(p.property_price_building).replace(",", ""))

        b = split_vat(
            gross_amount=bld_gross,
            vat_rate=self.vat_rate,
            non_taxable_ratio=self.non_taxable_ratio
        )

        b_net = b["tax_base"]
        b_vat_d = b["vat_deductible"]      # 控除可能
        b_vat_nd = b["vat_nondeductible"]  # 非課税 → 建物に算入


        # --- 建物（本体部分）
        if b_net > 0:
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="建物",
                credit_account="預金",
                amount=b_net
            ))

        # --- 建物の消費税（控除可能分）
        if b_vat_d > 0:
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="仮払消費税",
                credit_account="預金",
                amount=b_vat_d
            ))

        # --- 建物の消費税（控除不可 → 建物へ）
        if b_vat_nd > 0:
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="建物",
                credit_account="預金",
                amount=b_vat_nd
            ))
            b_net += b_vat_nd


        # ======================================================
        # 2) 土地（非課税）
        # ======================================================
        land = float(str(p.property_price_land).replace(",", ""))

        if land > 0:
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="土地",
                credit_account="預金",
                amount=land
            ))


        # ======================================================
        # 3) 仲介手数料（税込）
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
            bld_add = alloc["building_cost_addition"]

            vat_d = alloc["vat_deductible"]
            vat_nd = alloc["vat_nondeductible"]

            # --- 土地へ加算
            if land_add > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="土地",
                    credit_account="預金",
                    amount=land_add
                ))

            # --- 建物へ加算
            if bld_add > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="建物",
                    credit_account="預金",
                    amount=bld_add
                ))
                b_net += bld_add

            # --- 仲介手数料の VAT（控除可能）
            if vat_d > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="仮払消費税",
                    credit_account="預金",
                    amount=vat_d
                ))

            # --- 仲介手数料の VAT（控除不可）
            if vat_nd > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="建物",
                    credit_account="預金",
                    amount=vat_nd
                ))
                b_net += vat_nd


        # ======================================================
        # 4) 減価償却ユニット登録（建物）
        # ======================================================
        if b_net > 0:
            unit = DepreciationUnit(
                acquisition_cost=b_net,
                useful_life_years=int(p.building_useful_life),
                start_year=d0.year,
                start_month=d0.month,
                asset_type="building"
            )
            self.ledger.register_depreciation_unit(unit)


        # ======================================================
        # 5) 元入金
        # ======================================================
        if p.initial_equity > 0:
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="預金",
                credit_account="元入金",
                amount=p.initial_equity
            ))


        # ======================================================
        # 6) 借入金受取
        # ======================================================
        if p.initial_loan:

            amt = p.initial_loan.amount

            if amt > 0:
                loan = LoanEngine(
                    amount=amt,
                    annual_rate=p.initial_loan.interest_rate,
                    years=p.initial_loan.years
                )
                self.ledger.register_loan_unit(loan)

                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="預金",
                    credit_account="借入金",
                    amount=amt
                ))


        # ======================================================
        # 7) ★★ 追加投資（複数対応・現行仕様に完全準拠）★★
        # ======================================================
        if hasattr(p, "additional_investments") and p.additional_investments:

            for inv in p.additional_investments:

                add_gross = float(str(inv.amount).replace(",", ""))

                if add_gross <= 0:
                    continue

                # 発生年月（投資 year は 1 → start_date.year）
                y = d0.year + inv.year - 1
                m = d0.month
                dt_add = date(y, m, 1)

                # VAT 分解
                add = split_vat(
                    gross_amount=add_gross,
                    vat_rate=self.vat_rate,
                    non_taxable_ratio=self.non_taxable_ratio
                )

                add_net = add["tax_base"]
                add_vat_d = add["vat_deductible"]
                add_vat_nd = add["vat_nondeductible"]

                # --- 追加設備（税抜本体）
                self.ledger.add_entries(make_entry_pair(
                    date=dt_add,
                    debit_account="追加設備",
                    credit_account="預金",
                    amount=add_net
                ))

                # --- VAT：控除可能
                if add_vat_d > 0:
                    self.ledger.add_entries(make_entry_pair(
                        date=dt_add,
                        debit_account="仮払消費税",
                        credit_account="預金",
                        amount=add_vat_d
                    ))

                # --- VAT：控除不可 → 原価算入
                if add_vat_nd > 0:
                    self.ledger.add_entries(make_entry_pair(
                        date=dt_add,
                        debit_account="追加設備",
                        credit_account="預金",
                        amount=add_vat_nd
                    ))
                    add_net += add_vat_nd

                # --- 減価償却ユニット登録
                unit_add = DepreciationUnit(
                    acquisition_cost=add_net,
                    useful_life_years=int(inv.life),
                    start_year=y,
                    start_month=m,
                    asset_type="additional"
                )
                self.ledger.register_depreciation_unit(unit_add)


        # ======================================================
        # ★ return は最後に置く
        # ======================================================
        return True

# END