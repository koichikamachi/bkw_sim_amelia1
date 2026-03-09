# ============================================================
# core/bookkeeping/monthly_entries.py
# 仕様書 第6章 Monthly Engine 準拠版
# ============================================================

from datetime import date
from core.tax.tax_splitter import split_vat
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanUnit
from core.ledger.journal_entry import make_entry_pair


class MonthlyEntryGenerator:
    """
    仕様書 第6章 Monthly Engine

    毎月の仕訳生成を担当する。
    自身は計算ロジックを持たず、各ユニット（LoanUnit, DepreciationUnit）
    に計算を委譲し、結果をledgerに記帳するのみ。

    処理順序（仕様書6.1節）：
        1. 家賃収入（税抜 + 仮受消費税）
        2. 管理費（管理費を個別科目で起票）
        3. 修繕費（個別科目）
        4. 保険料（個別科目・非課税）
        5. その他販管費（個別科目）
        3. 固定資産税（土地・建物 別科目）
        4. 追加設備取得（投資年月に一致する場合のみ）
        5. 減価償却（建物・追加設備）
        6. 借入返済（利息 + 元金）
    """

    def __init__(self, params, ledger, calendar_mapper):
        self.p = params
        self.ledger = ledger
        self.map_sim_to_calendar = calendar_mapper

        self.vat_rate          = float(params.consumption_tax_rate)
        self.non_taxable_ratio = float(params.non_taxable_proportion)
        self.taxable_ratio     = 1.0 - self.non_taxable_ratio

    # ============================================================
    # 月次仕訳生成メイン（仕様書6.2節 generate(sim_month_index)）
    # ============================================================
    def generate(self, sim_month_index: int) -> bool:

        d0 = self.map_sim_to_calendar(sim_month_index)
        p  = self.p

        # シミュレーション年（1始まり）
        sim_year  = (sim_month_index - 1) // 12 + 1
        sim_month = (sim_month_index - 1) % 12 + 1

        # ============================================================
        # 1) 家賃収入（税込 → 税抜 + 仮受消費税）
        # ============================================================
        if p.monthly_rent_incl > 0:
            r = split_vat(
                gross_amount=float(p.monthly_rent_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            # 税抜家賃
            self.ledger.add_entries(make_entry_pair(
                d0, "預金", "売上高", r["tax_base"]
            ))
            # 仮受消費税
            if r["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "預金", "仮受消費税", r["vat_deductible"]
                ))

        # ============================================================
        # 2) 管理費（税込 → 管理費 + VAT）
        # ============================================================
        if p.monthly_admin_cost_incl > 0:
            a = split_vat(
                gross_amount=float(p.monthly_admin_cost_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            self.ledger.add_entries(make_entry_pair(
                d0, "管理費", "預金", a["tax_base"]
            ))
            if a["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "仮払消費税", "預金", a["vat_deductible"]
                ))
            # 控除不能 VAT → 租税公課（消費税）
            if a["vat_nondeductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "租税公課（消費税）", "預金", a["vat_nondeductible"]
                ))

        # ============================================================
        # 3) 修繕費（税込 → 修繕費 + VAT）
        # ============================================================
        if p.monthly_repair_cost_incl > 0:
            s = split_vat(
                gross_amount=float(p.monthly_repair_cost_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            self.ledger.add_entries(make_entry_pair(
                d0, "修繕費", "預金", s["tax_base"]
            ))
            if s["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "仮払消費税", "預金", s["vat_deductible"]
                ))
            if s["vat_nondeductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "租税公課（消費税）", "預金", s["vat_nondeductible"]
                ))

        # ============================================================
        # 4) 保険料（非課税・仮払消費税なし）
        # ============================================================
        if p.monthly_insurance_cost > 0:
            self.ledger.add_entries(make_entry_pair(
                d0, "保険料", "預金", float(p.monthly_insurance_cost)
            ))

        # ============================================================
        # 5) その他販管費（税込 → その他販管費 + VAT）
        # ============================================================
        if p.monthly_other_management_cost > 0:
            o = split_vat(
                gross_amount=float(p.monthly_other_management_cost),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            self.ledger.add_entries(make_entry_pair(
                d0, "その他販管費", "預金", o["tax_base"]
            ))
            if o["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "仮払消費税", "預金", o["vat_deductible"]
                ))
            if o["vat_nondeductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "租税公課（消費税）", "預金", o["vat_nondeductible"]
                ))

        # ============================================================
        # 6) 固定資産税（土地・建物 別科目・非課税）
        #    月次按分（年額 ÷ 12）
        # ============================================================
        monthly_fa_land = p.fixed_asset_tax_land / 12
        monthly_fa_bld  = p.fixed_asset_tax_building / 12

        if monthly_fa_land > 0:
            self.ledger.add_entries(make_entry_pair(
                d0, "固定資産税（土地）", "預金", monthly_fa_land
            ))
        if monthly_fa_bld > 0:
            self.ledger.add_entries(make_entry_pair(
                d0, "固定資産税（建物）", "預金", monthly_fa_bld
            ))

        # ============================================================
        # 7) 追加設備取得（投資年・月が一致する場合のみ）
        #    フィールド名：inv.year / inv.amount / inv.life（仕様書統一表）
        # ============================================================
        if p.additional_investments:
            for inv in p.additional_investments:
                # AdditionalInvestmentParams は year フィールドのみ（月は1月固定）
                if inv.year == sim_year and sim_month == 1:

                    gross    = float(inv.amount)
                    add_split = split_vat(
                        gross_amount=gross,
                        vat_rate=self.vat_rate,
                        non_taxable_ratio=self.non_taxable_ratio,
                    )
                    add_net    = add_split["tax_base"]
                    add_vat_d  = add_split["vat_deductible"]
                    add_vat_nd = add_split["vat_nondeductible"]

                    # 追加設備本体（税抜）
                    self.ledger.add_entries(make_entry_pair(
                        d0, "追加設備", "預金", add_net
                    ))
                    # 控除可能 VAT
                    if add_vat_d > 0:
                        self.ledger.add_entries(make_entry_pair(
                            d0, "仮払消費税", "預金", add_vat_d
                        ))
                    # 控除不能 VAT → 取得原価に算入
                    if add_vat_nd > 0:
                        self.ledger.add_entries(make_entry_pair(
                            d0, "追加設備", "預金", add_vat_nd
                        ))
                        add_net += add_vat_nd  # 償却対象原価に加算

                    # 付随借入金（loan_amount > 0 の場合）
                    add_loan_amt = float(getattr(inv, "loan_amount", 0) or 0)
                    if add_loan_amt > 0:
                        # 借入受取仕訳：預金 / 追加設備投資借入金
                        self.ledger.add_entries(make_entry_pair(
                            d0, "預金", "追加設備投資借入金", add_loan_amt
                        ))
                        # LoanUnit 登録（月次返済に使用）
                        add_loan_unit = LoanUnit(
                            amount=add_loan_amt,
                            annual_rate=float(getattr(inv, "loan_interest_rate", 0) or 0),
                            years=int(getattr(inv, "loan_years", 1) or 1),
                            start_sim_month=sim_month_index,
                            repayment_method="annuity",
                            loan_type="additional",
                        )
                        self.ledger.loan_units.append(add_loan_unit)

                    # 減価償却ユニット登録
                    unit_add = DepreciationUnit(
                        acquisition_cost=add_net,
                        useful_life_years=int(inv.life),
                        start_year=d0.year,
                        start_month=d0.month,
                        asset_type="additional",
                    )
                    self.ledger.register_depreciation_unit(unit_add)

        # ============================================================
        # 8) 減価償却（仕様書6.2節 post_building_depreciation /
        #               post_additional_capex_depreciation）
        # ============================================================
        for unit in self.ledger.depreciation_units:
            if unit.is_active(d0.year, d0.month):
                amt = unit.monthly_amount()

                if unit.asset_type == "building":
                    dr_acct = "建物減価償却費"
                    cr_acct = "建物減価償却累計額"
                else:
                    dr_acct = "追加設備減価償却費"
                    cr_acct = "追加設備減価償却累計額"

                self.ledger.add_entries(make_entry_pair(
                    d0, dr_acct, cr_acct, amt
                ))

        # ============================================================
        # 9) 借入返済（利息 + 元金）
        #    科目名：初期ローン → 長期借入金利息 / 長期借入金
        #           追加設備ローン → 追加設備借入利息 / 追加設備投資借入金
        # ============================================================
        for loan in self.ledger.loan_units:
            if loan.is_active(sim_month_index):
                interest, principal = loan.monthly_payment()

                # 利息科目・元金科目をローン種別で切り替える
                if getattr(loan, "loan_type", "initial") == "additional":
                    interest_acct = "追加設備借入利息"
                    principal_acct = "追加設備投資借入金"
                else:
                    interest_acct = "長期借入金利息"
                    principal_acct = "長期借入金"

                if interest > 0:
                    self.ledger.add_entries(make_entry_pair(
                        d0, interest_acct, "預金", interest
                    ))
                if principal > 0:
                    self.ledger.add_entries(make_entry_pair(
                        d0, principal_acct, "預金", principal
                    ))

        return True

# ============================================================
# core/bookkeeping/monthly_entries.py end
# ============================================================