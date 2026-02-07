# ============================================================
# core/bookkeeping/monthly_entries.py（完全修正版）
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

        # Simulation (calendar conversion bridge)
        self.simulation = None

        # Monthly expenses
        self.monthly_rent = params.annual_rent_income_incl / 12.0
        self.monthly_mgmt_fee = params.annual_management_fee_initial / 12.0
        self.monthly_repair_cost = params.repair_cost_annual / 12.0

        # VAT
        self.vat_rate = params.consumption_tax_rate
        self.non_taxable_ratio = params.non_taxable_proportion

        # Annual totals
        self.vat_received = 0.0
        self.vat_paid = 0.0
        self.monthly_profit_total = 0.0

        # Additional investments
        self.additional_investments = params.additional_investments


    # ============================================================
    # 月次生成メイン
    # ============================================================
    def generate_month(self, year: int, month: int):

        # ------------------------------------------------------------
        # 1) 正しい「その月」の実カレンダー年月を決定（上書き禁止）
        # ------------------------------------------------------------
        if self.simulation is not None:
            cal_y, cal_m = self.simulation.map_sim_to_calendar(year, month)
        else:
            cal_y = self.start_date.year + (year - 1)
            cal_m = month

        dt = date(cal_y, cal_m, 1)
        p = self.p

        # ------------------------------------------------------------
        # ★ デバッグログ（必要最小限）
        # ------------------------------------------------------------
        print(f"[MONTH] sim={year}-{month} → cal={cal_y}-{cal_m}")
        print("DEPR UNITS:", self.ledger.get_depreciation_units())

        # ------------------------------------------------------------
        # 2) 追加投資（当該年の1月だけ適用）
        # ------------------------------------------------------------
        for inv in self.additional_investments:

            if inv.invest_year == year and month == 1:

                inv_amount = float(inv.invest_amount)
                life = int(inv.depreciation_years)

                # 投資のための専用カレンダー値（絶対に cal_y/cal_m を上書きしない）
                inv_cal_y, inv_cal_m = self.simulation.map_sim_to_calendar(year, month)
                dt_inv = date(inv_cal_y, inv_cal_m, 1)

                # VAT
                taxinfo = split_vat(
                    gross_amount=inv_amount,
                    vat_rate=self.vat_rate,
                    non_taxable_ratio=self.non_taxable_ratio
                )

                base = taxinfo["tax_base"]
                vat_deductible = taxinfo["vat_deductible"]
                vat_non = taxinfo["vat_nondeductible"]

                acquisition_cost = base + vat_non

                # --- 原価計上 ---
                self.ledger.add_entries(make_entry_pair(
                    dt_inv, "追加設備", "預金", acquisition_cost
                ))

                # --- 仮払消費税 ---
                if vat_deductible > 0:
                    self.ledger.add_entries(make_entry_pair(
                        dt_inv, "仮払消費税", "預金", vat_deductible
                    ))
                    self.vat_paid += vat_deductible

                # --- 追加設備 減価償却ユニット登録 ---
                unit = DepreciationUnit(
                    acquisition_cost=acquisition_cost,
                    useful_life_years=life,
                    start_year=inv_cal_y,
                    start_month=inv_cal_m,
                    asset_type="additional_asset",
                )
                self.ledger.register_depreciation_unit(unit)

        # ------------------------------------------------------------
        # 3) 家賃収入（税込）
        # ------------------------------------------------------------
        if self.monthly_rent > 0:

            taxinfo = split_vat(
                gross_amount=self.monthly_rent,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
                # 🔥🔥 ここに入れる（必ず！）🔥🔥
            print("MONTHLY RENT:", self.monthly_rent)
            print("VAT SPLIT:", taxinfo)

            import streamlit as st
            st.write(f"MONTHLY RENT: {self.monthly_rent}")
            st.write(f"VAT SPLIT: {taxinfo}")

            base = taxinfo["tax_base"]
            vat = taxinfo["vat_deductible"]

            if base > 0:
                self.ledger.add_entries(make_entry_pair(dt, "預金", "売上高", base))
                self.monthly_profit_total += base

            if vat > 0:
                self.ledger.add_entries(make_entry_pair(dt, "預金", "仮受消費税", vat))
                self.vat_received += vat

        # ------------------------------------------------------------
        # 4) 管理費（税込）
        # ------------------------------------------------------------
        if self.monthly_mgmt_fee > 0:

            entries = build_periodic_expense_entries(
                date=dt,
                account_name="販売費一般管理費",
                gross_amount=self.monthly_mgmt_fee,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )

            if isinstance(entries, JournalEntry):
                entries = [entries]

            self.ledger.add_entries(entries)

            for e in entries:
                if e.dr_account == "仮払消費税":
                    self.vat_paid += e.dr_amount
                elif e.dr_account == "販売費一般管理費":
                    self.monthly_profit_total -= e.dr_amount

        # ------------------------------------------------------------
        # 5) 修繕費（税込）
        # ------------------------------------------------------------
        if self.monthly_repair_cost > 0:

            entries = build_periodic_expense_entries(
                date=dt,
                account_name="販売費一般管理費",
                gross_amount=self.monthly_repair_cost,
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )

            if isinstance(entries, JournalEntry):
                entries = [entries]

            self.ledger.add_entries(entries)

            for e in entries:
                if e.dr_account == "仮払消費税":
                    self.vat_paid += e.dr_amount
                elif e.dr_account == "販売費一般管理費":
                    self.monthly_profit_total -= e.dr_amount

        # ------------------------------------------------------------
        # 6) 固定資産税（非課税）
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
        # 7) 減価償却（cal_y / cal_m を必ず使う）
        # ------------------------------------------------------------
        for u in self.ledger.get_depreciation_units():

            amount = u.get_monthly_depreciation(cal_y, cal_m)

            if amount > 0:

                if u.asset_type == "building":
                    dr = "建物減価償却費"
                    cr = "建物減価償却累計額"
                else:
                    dr = "追加設備減価償却費"
                    cr = "追加設備減価償却累計額"

                self.ledger.add_entries(make_entry_pair(dt, dr, cr, amount))
                self.monthly_profit_total -= amount

        # ------------------------------------------------------------
        # 8) 借入返済
        # ------------------------------------------------------------
        for loan in self.ledger.get_loan_units():

            idx = (year - 1) * 12 + month
            detail = loan.calculate_monthly_payment(idx)
            if not detail:
                continue

            interest = detail["interest"]
            principal = detail["principal"]

            if interest > 0:
                self.ledger.add_entries(make_entry_pair(dt, "支払利息", "預金", interest))
                self.monthly_profit_total -= interest

            if principal > 0:
                self.ledger.add_entries(make_entry_pair(dt, "借入金", "預金", principal))

        return True