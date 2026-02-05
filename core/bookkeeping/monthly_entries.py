# ============================================================
# core/bookkeeping/monthly_entries.py（完全VAT対応＋追加投資対応・修正版）
# ============================================================

from datetime import date
from core.ledger.journal_entry import make_entry_pair, JournalEntry
from core.depreciation.unit import DepreciationUnit
from core.tax.tax_splitter import split_vat
from core.tax.periodic_expense_vat_builder import build_periodic_expense_entries


class MonthlyEntryGenerator:

    def __init__(self, params, ledger, start_date):
        self.p = params
        self.ledger = ledger
        self.start_date = start_date

        # Simulation との接続（暦変換のために simulation.map_sim_to_calendar を使う）
        self.simulation = None  # Simulation.run() 内で monthly.simulation = self が設定される

        # 月額計算
        self.monthly_rent = params.annual_rent_income_incl / 12.0
        self.monthly_mgmt_fee = params.annual_management_fee_initial / 12.0
        self.monthly_repair_cost = params.repair_cost_annual / 12.0

        # VAT
        self.vat_rate = params.consumption_tax_rate
        self.non_taxable_ratio = params.non_taxable_proportion

        # 年間集計
        self.vat_received = 0.0
        self.vat_paid = 0.0
        self.monthly_profit_total = 0.0

        # 追加投資
        self.additional_investments = params.additional_investments


    # ============================================================
    # 月次生成メイン
    # ============================================================
    def generate_month(self, year: int, month: int):
    
        # ------------------------------------------------------------
        # 暦変換（まずこれを計算してから print する）
        # ------------------------------------------------------------
        if self.simulation is not None:
            cal_year, cal_month = self.simulation.map_sim_to_calendar(year, month)
        else:
            cal_year = self.start_date.year + (year - 1)
            cal_month = month
    
        # --- LOG ---
        print("GEN MONTH:", year, month)
        print("CAL:", cal_year, cal_month)
        print("DEPR UNITS:", self.ledger.get_depreciation_units())
    
        dt = date(cal_year, cal_month, 1)
        p = self.p

        # ------------------------------------------------------------
        # ★ 1) 追加投資の取得仕訳（VAT 完全対応）
        # ------------------------------------------------------------
        for inv in self.additional_investments:
            # if inv.invest_year == year and month == 1:
            if inv.invest_year == year and month == 1:
                amount_gross = float(inv.invest_amount)
                life = int(inv.depreciation_years)

                taxinfo = split_vat(
                    gross_amount=amount_gross,
                    vat_rate=self.vat_rate,
                    non_taxable_ratio=self.non_taxable_ratio
                )

                base = taxinfo["tax_base"]
                vat_deductible = taxinfo["vat_deductible"]
                vat_nondeductible = taxinfo["vat_nondeductible"]

                acquisition_cost = base + vat_nondeductible

                # (A) 原価計上
                self.ledger.add_entries(make_entry_pair(
                    dt,
                    dr_account="追加設備",
                    cr_account="現金",
                    amount=acquisition_cost
                ))

                # (B) 仮払消費税（控除可能）
                if vat_deductible > 0:
                    self.ledger.add_entries(make_entry_pair(
                        dt,
                        dr_account="仮払消費税",
                        cr_account="現金",
                        amount=vat_deductible
                    ))
                    self.vat_paid += vat_deductible

                # (C) 減価償却ユニット登録
                unit = DepreciationUnit(
                    acquisition_cost=acquisition_cost,
                    useful_life_years=life,
                    start_year=dt.year,
                    start_month=dt.month,
                    asset_type="additional_asset"
                )
                self.ledger.register_depreciation_unit(unit)

        # ------------------------------------------------------------
        # ★ 2) 家賃収入（税込）
        # ------------------------------------------------------------
        if self.monthly_rent > 0:

            taxinfo = split_vat(
                gross_amount=self.monthly_rent,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )

            base = taxinfo["tax_base"]
            vat = taxinfo["vat_deductible"]

            if base > 0:
                self.ledger.add_entries(
                    make_entry_pair(dt, "預金", "売上高", base)
                )
                self.monthly_profit_total += base

            if vat > 0:
                self.ledger.add_entries(
                    make_entry_pair(dt, "預金", "仮受消費税", vat)
                )
                self.vat_received += vat

        # ------------------------------------------------------------
        # ★ 3) 管理費（税込）
        # ------------------------------------------------------------
        if self.monthly_mgmt_fee > 0:

            entries = build_periodic_expense_entries(
                date=dt,
                account_name="販売費一般管理費",
                gross_amount=self.monthly_mgmt_fee,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio
            )

            if isinstance(entries, JournalEntry):
                entries = [entries]

            self.ledger.add_entries(entries)

            for e in entries:
                if e.dr_account == "仮払消費税":
                    self.vat_paid += e.dr_amount
                if e.dr_account == "販売費一般管理費":
                    self.monthly_profit_total -= e.dr_amount

        # ------------------------------------------------------------
        # ★ 4) 修繕費（税込）
        # ------------------------------------------------------------
        if self.monthly_repair_cost > 0:

            entries = build_periodic_expense_entries(
                date=dt,
                account_name="販売費一般管理費",
                gross_amount=self.monthly_repair_cost,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio
            )

            if isinstance(entries, JournalEntry):
                entries = [entries]

            self.ledger.add_entries(entries)

            for e in entries:
                if e.dr_account == "仮払消費税":
                    self.vat_paid += e.dr_amount
                if e.dr_account == "販売費一般管理費":
                    self.monthly_profit_total -= e.dr_amount

        # ------------------------------------------------------------
        # ★ 5) 固定資産税（非課税）
        # ------------------------------------------------------------
        if month == 4:

            if p.fixed_asset_tax_land > 0:
                self.ledger.add_entries(make_entry_pair(
                    dt, "租税公課（固定資産税）", "預金", p.fixed_asset_tax_land
                ))
                self.monthly_profit_total -= p.fixed_asset_tax_land

            if p.fixed_asset_tax_building > 0:
                self.ledger.add_entries(make_entry_pair(
                    dt, "租税公課（固定資産税）", "預金", p.fixed_asset_tax_building
                ))
                self.monthly_profit_total -= p.fixed_asset_tax_building


        # ------------------------------------------------------------
        # ★ 減価償却（ログ付き）
        # ------------------------------------------------------------
        print("ENTER DEPRECIATION BLOCK")
    
        for u in self.ledger.get_depreciation_units():
    
            amount = u.get_monthly_depreciation(cal_year, cal_month)
    
            print("DEPR:", u.asset_type, "→", amount)
    
            if amount <= 0:
                continue
    
            if u.asset_type == "building":
                dr = "建物減価償却費"
                cr = "建物減価償却累計額"
            else:
                dr = "追加設備減価償却費"
                cr = "追加設備減価償却累計額"
    
            self.ledger.add_entries(make_entry_pair(dt, dr, cr, amount))
            self.monthly_profit_total -= amount

        # ------------------------------------------------------------
        # ★ 7) 借入返済
        # ------------------------------------------------------------
        for loan in self.ledger.get_loan_units():

            idx = (year - 1) * 12 + month
            detail = loan.calculate_monthly_payment(idx)
            if not detail:
                continue

            interest = detail["interest"]
            principal = detail["principal"]

            if interest > 0:
                self.ledger.add_entries(
                    make_entry_pair(dt, "支払利息", "預金", interest)
                )
                self.monthly_profit_total -= interest

            if principal > 0:
                self.ledger.add_entries(
                    make_entry_pair(dt, "借入金", "預金", principal)
                )

        return True


# ============================================================
# END monthly_entries.py（完全修正版）
# ============================================================