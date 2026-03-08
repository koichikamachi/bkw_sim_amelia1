# ============================================================
# core/bookkeeping/monthly_entries.py
# 仕様書 第6章 Monthly Engine 準拠版
# ============================================================
#
# 【処理順序（仕様書6.1節）】
#   1. 家賃収入（税抜 + 仮受消費税）
#   2. 管理費（税込 → 販売費一般管理費 + VAT）
#   3. 修繕費（税込 → 修繕費 + VAT）
#   4. 保険料（非課税・VAT分離なし）
#   5. その他販管費（税込 → その他販管費 + VAT）
#   6. 固定資産税（土地・建物 別科目・非課税・年額÷12）
#   7. 追加設備取得（投資年・1月のみ）＋ 付随借入金の受取・LoanUnit登録
#   8. 減価償却（建物・追加設備）
#   9. 借入返済（利息 + 元金）← ローン種別で科目名を切替
#  10. 当座借越チェック（月末預金残高がマイナスなら借越・プラスなら返済）
#
# ============================================================

from datetime import date
from core.tax.tax_splitter import split_vat
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanUnit
from core.ledger.journal_entry import make_entry_pair


class MonthlyEntryGenerator:

    def __init__(self, params, ledger, calendar_mapper):
        self.p = params
        self.ledger = ledger
        self.map_sim_to_calendar = calendar_mapper
        self.vat_rate          = float(params.consumption_tax_rate)
        self.non_taxable_ratio = float(params.non_taxable_proportion)
        self.taxable_ratio     = 1.0 - self.non_taxable_ratio

    def generate(self, sim_month_index: int) -> bool:
        d0 = self.map_sim_to_calendar(sim_month_index)
        p  = self.p
        sim_year  = (sim_month_index - 1) // 12 + 1
        sim_month = (sim_month_index - 1) % 12 + 1

        # 1) 家賃収入
        if p.monthly_rent_incl > 0:
            r = split_vat(float(p.monthly_rent_incl), self.vat_rate, self.non_taxable_ratio)
            self.ledger.add_entries(make_entry_pair(d0, "預金", "売上高", r["tax_base"]))
            if r["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(d0, "預金", "仮受消費税", r["vat_deductible"]))

        # 2) 管理費
        if p.monthly_admin_cost_incl > 0:
            a = split_vat(float(p.monthly_admin_cost_incl), self.vat_rate, self.non_taxable_ratio)
            self.ledger.add_entries(make_entry_pair(d0, "販売費一般管理費", "預金", a["tax_base"]))
            if a["vat_deductible"]    > 0: self.ledger.add_entries(make_entry_pair(d0, "仮払消費税",       "預金", a["vat_deductible"]))
            if a["vat_nondeductible"] > 0: self.ledger.add_entries(make_entry_pair(d0, "租税公課（消費税）", "預金", a["vat_nondeductible"]))

        # 3) 修繕費
        if p.monthly_repair_cost_incl > 0:
            s = split_vat(float(p.monthly_repair_cost_incl), self.vat_rate, self.non_taxable_ratio)
            self.ledger.add_entries(make_entry_pair(d0, "修繕費", "預金", s["tax_base"]))
            if s["vat_deductible"]    > 0: self.ledger.add_entries(make_entry_pair(d0, "仮払消費税",       "預金", s["vat_deductible"]))
            if s["vat_nondeductible"] > 0: self.ledger.add_entries(make_entry_pair(d0, "租税公課（消費税）", "預金", s["vat_nondeductible"]))

        # 4) 保険料（非課税）
        if p.monthly_insurance_cost > 0:
            self.ledger.add_entries(make_entry_pair(d0, "販売費一般管理費", "預金", float(p.monthly_insurance_cost)))

        # 5) その他販管費
        if p.monthly_other_management_cost > 0:
            o = split_vat(float(p.monthly_other_management_cost), self.vat_rate, self.non_taxable_ratio)
            self.ledger.add_entries(make_entry_pair(d0, "その他販管費", "預金", o["tax_base"]))
            if o["vat_deductible"]    > 0: self.ledger.add_entries(make_entry_pair(d0, "仮払消費税",       "預金", o["vat_deductible"]))
            if o["vat_nondeductible"] > 0: self.ledger.add_entries(make_entry_pair(d0, "租税公課（消費税）", "預金", o["vat_nondeductible"]))

        # 6) 固定資産税（非課税）
        if p.fixed_asset_tax_land / 12 > 0:
            self.ledger.add_entries(make_entry_pair(d0, "固定資産税（土地）", "預金", p.fixed_asset_tax_land / 12))
        if p.fixed_asset_tax_building / 12 > 0:
            self.ledger.add_entries(make_entry_pair(d0, "固定資産税（建物）", "預金", p.fixed_asset_tax_building / 12))

        # 7) 追加設備取得（投資年の1月のみ）
        if p.additional_investments:
            for inv in p.additional_investments:
                if inv.year == sim_year and sim_month == 1:
                    add_split = split_vat(float(inv.amount), self.vat_rate, self.non_taxable_ratio)
                    add_net    = add_split["tax_base"]
                    add_vat_d  = add_split["vat_deductible"]
                    add_vat_nd = add_split["vat_nondeductible"]

                    self.ledger.add_entries(make_entry_pair(d0, "追加設備", "預金", add_net))
                    if add_vat_d  > 0: self.ledger.add_entries(make_entry_pair(d0, "仮払消費税", "預金", add_vat_d))
                    if add_vat_nd > 0:
                        self.ledger.add_entries(make_entry_pair(d0, "追加設備", "預金", add_vat_nd))
                        add_net += add_vat_nd

                    self.ledger.register_depreciation_unit(DepreciationUnit(
                        acquisition_cost=add_net,
                        useful_life_years=int(inv.life),
                        start_year=d0.year,
                        start_month=d0.month,
                        asset_type="additional",
                    ))

                    if inv.loan_amount > 0:
                        self.ledger.add_entries(make_entry_pair(d0, "預金", "追加設備投資借入金", inv.loan_amount))
                        self.ledger.register_loan_unit(LoanUnit(
                            amount=inv.loan_amount,
                            annual_rate=inv.loan_interest_rate,
                            years=inv.loan_years if inv.loan_years > 0 else 1,
                            repayment_method="annuity",
                            loan_type="additional",
                            start_sim_month=sim_month_index,
                        ))

        # 8) 減価償却
        for unit in self.ledger.depreciation_units:
            if unit.is_active(d0.year, d0.month):
                amt    = unit.monthly_amount()
                dr_acc = "建物減価償却費"     if unit.asset_type == "building" else "追加設備減価償却費"
                cr_acc = "建物減価償却累計額"  if unit.asset_type == "building" else "追加設備減価償却累計額"
                self.ledger.add_entries(make_entry_pair(d0, dr_acc, cr_acc, amt))

        # 9) 借入返済
        for loan in self.ledger.loan_units:
            if loan.is_active(sim_month_index):
                interest, principal = loan.monthly_payment()
                if getattr(loan, "loan_type", "initial") == "additional":
                    i_acc, p_acc = "追加設備借入利息", "追加設備投資借入金"
                else:
                    i_acc, p_acc = "長期借入金利息", "長期借入金"
                if interest  > 0: self.ledger.add_entries(make_entry_pair(d0, i_acc, "預金", interest))
                if principal > 0: self.ledger.add_entries(make_entry_pair(d0, p_acc, "預金", principal))

        # ============================================================
        # 10) 当座借越チェック（仕様書6.3節）
        #
        #  【処理フロー】
        #   ① 既存の当座借越残高に対して月次利息を計上（残高>0のとき）
        #      借）当座借越利息   ／ 貸）預金
        #   ② 利息計上後の月末預金残高を計算
        #   ③ 預金残高 < 0 → 超過分を当座借越で補填
        #      借）預金           ／ 貸）当座借越借入金
        #   ④ 預金残高 > 0 かつ当座借越残あり → 可能な限り返済
        #      借）当座借越借入金 ／ 貸）預金
        #
        #  ※ 利息計上後に再度預金がマイナスになる場合も
        #    ③で補填されるため二重チェックは不要。
        # ============================================================
        overdraft_rate = float(getattr(p, "overdraft_interest_rate", 0.02))

        # ① 当座借越残高の取得と利息計上
        def _od_balance():
            df = self.ledger.get_df()
            d  = df[df["account"] == "当座借越借入金"]
            return float(d[d["dr_cr"] == "credit"]["amount"].sum()
                       - d[d["dr_cr"] == "debit" ]["amount"].sum())

        def _cash_balance():
            df = self.ledger.get_df()
            c  = df[df["account"] == "預金"]
            return float(c[c["dr_cr"] == "debit" ]["amount"].sum()
                       - c[c["dr_cr"] == "credit"]["amount"].sum())

        od_bal = _od_balance()
        if od_bal > 0:
            od_interest = round(od_bal * (overdraft_rate / 12))
            if od_interest > 0:
                self.ledger.add_entries(make_entry_pair(d0, "当座借越利息", "預金", od_interest))

        # ② 月末預金残高チェック
        cash = _cash_balance()

        if cash < 0:
            # ③ 借越補填
            self.ledger.add_entries(make_entry_pair(d0, "預金", "当座借越借入金", -cash))

        elif cash > 0:
            # ④ 借越返済（可能な限り）
            od_bal = _od_balance()   # 利息計上後の最新残高
            if od_bal > 0:
                repay = min(cash, od_bal)
                self.ledger.add_entries(make_entry_pair(d0, "当座借越借入金", "預金", repay))

        return True

# ============================================================
# core/bookkeeping/monthly_entries.py end
# ============================================================