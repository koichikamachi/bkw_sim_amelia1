# ============================================================
# core/bookkeeping/monthly_entries.py
# ============================================================
from datetime import date
from core.tax.tax_splitter import split_vat
from core.engine.loan_engine import LoanEngine
from core.depreciation.unit import DepreciationUnit
from core.ledger.journal_entry import make_entry_pair


class MonthlyEntryGenerator:

    def __init__(self, params, ledger, calendar_mapper):
        self.p = params
        self.ledger = ledger

        # ❗️ここだけが重要な修正ポイント
        # Simulation 側で monthly = MonthlyEntryGenerator(..., calendar_mapper=self.map_sim_to_calendar)
        # と渡されるため、シグネチャに合わせて保持する
        self.map_sim_to_calendar = calendar_mapper

        self.vat_rate = float(params.consumption_tax_rate)
        self.non_taxable_ratio = float(params.non_taxable_proportion)
        self.taxable_ratio = 1 - self.non_taxable_ratio


    # ============================================================
    # 月次仕訳生成メイン
    # ============================================================
    def generate(self, sim_month_index: int):

        # ❗️Simulation → calendar のマッピング
        d0 = self.map_sim_to_calendar(sim_month_index)

        p = self.p

        # ============================================================
        # 1) 家賃収入（税込）→ 税抜 + VAT
        # ============================================================
        if p.monthly_rent_incl > 0:

            r = split_vat(
                gross_amount=float(p.monthly_rent_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio
            )

            rent_net = r["tax_base"]
            rent_vat = r["vat_deductible"]     # 受取 VAT（課税売上）

            # --- 税抜家賃
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="預金",
                credit_account="売上高",
                amount=rent_net
            ))

            # --- 仮受消費税
            if rent_vat > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="預金",
                    credit_account="仮受消費税",
                    amount=rent_vat
                ))


        # ============================================================
        # 2) 管理費（税込）→ 課税仕入れ（課税割合で控除可/不可）
        # ============================================================
        if p.monthly_admin_cost_incl > 0:

            a = split_vat(
                gross_amount=float(p.monthly_admin_cost_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio
            )

            admin_net = a["tax_base"]
            admin_vat_d = a["vat_deductible"]
            admin_vat_nd = a["vat_nondeductible"]

            # --- 費用（税抜）
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="管理費",
                credit_account="預金",
                amount=admin_net
            ))

            # --- 控除可能 VAT
            if admin_vat_d > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="仮払消費税",
                    credit_account="預金",
                    amount=admin_vat_d
                ))

            # --- 控除不可 VAT → 租税公課へ
            if admin_vat_nd > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="租税公課",
                    credit_account="預金",
                    amount=admin_vat_nd
                ))


        # ============================================================
        # 3) 修繕費（同様に VAT 対応）
        # ============================================================
        if p.monthly_repair_cost_incl > 0:

            s = split_vat(
                gross_amount=float(p.monthly_repair_cost_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio
            )

            rep_net = s["tax_base"]
            rep_vat_d = s["vat_deductible"]
            rep_vat_nd = s["vat_nondeductible"]

            # --- 修繕費（税抜）
            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="修繕費",
                credit_account="預金",
                amount=rep_net
            ))

            # --- 控除可能 VAT
            if rep_vat_d > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="仮払消費税",
                    credit_account="預金",
                    amount=rep_vat_d
                ))

            # --- 控除不可 VAT → 租税公課へ
            if rep_vat_nd > 0:
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="租税公課",
                    credit_account="預金",
                    amount=rep_vat_nd
                ))


        # ============================================================
        # 4) 固定資産税（非課税）
        # ============================================================
        if p.monthly_property_tax > 0:

            self.ledger.add_entries(make_entry_pair(
                date=d0,
                debit_account="租税公課",
                credit_account="預金",
                amount=float(p.monthly_property_tax)
            ))


        # ============================================================
        # 5) 期中追加設備（複数対応）
        # ============================================================
        if hasattr(p, "additional_investments") and p.additional_investments:

            for inv in p.additional_investments:

                if inv["year"] == d0.year and inv["month"] == d0.month:

                    gross = float(inv["amount"])

                    add = split_vat(
                        gross_amount=gross,
                        vat_rate=self.vat_rate,
                        non_taxable_ratio=self.non_taxable_ratio
                    )

                    add_net = add["tax_base"]
                    add_vat_d = add["vat_deductible"]
                    add_vat_nd = add["vat_nondeductible"]

                    # --- 追加設備（税抜本体）
                    self.ledger.add_entries(make_entry_pair(
                        date=d0,
                        debit_account="追加設備",
                        credit_account="預金",
                        amount=add_net
                    ))

                    # --- VAT：控除可能
                    if add_vat_d > 0:
                        self.ledger.add_entries(make_entry_pair(
                            date=d0,
                            debit_account="仮払消費税",
                            credit_account="預金",
                            amount=add_vat_d
                        ))

                    # --- VAT：控除不可 → 原価算入
                    if add_vat_nd > 0:
                        self.ledger.add_entries(make_entry_pair(
                            date=d0,
                            debit_account="追加設備",
                            credit_account="預金",
                            amount=add_vat_nd
                        ))
                        add_net += add_vat_nd

                    # --- 減価償却ユニット登録（追加設備）
                    unit_add = DepreciationUnit(
                        acquisition_cost=add_net,
                        useful_life_years=int(inv["life"]),
                        start_year=d0.year,
                        start_month=d0.month,
                        asset_type="additional"
                    )
                    self.ledger.register_depreciation_unit(unit_add)


        # ============================================================
        # 6) 減価償却（建物 + 複数追加設備）
        # ============================================================
        for unit in self.ledger.depreciation_units:

            if unit.is_active(d0.year, d0.month):

                amt = unit.monthly_amount()

                acct = "建物減価償却費" if unit.asset_type == "building" else "追加設備減価償却費"
                acct_accum = "建物減価償却累計額" if unit.asset_type == "building" else "追加設備減価償却累計額"

                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account=acct,
                    credit_account=acct_accum,
                    amount=amt
                ))


        # ============================================================
        # 7) 借入返済（利息 → 費用、本体 → 元金）
        # ============================================================
        for loan in self.ledger.loan_units:

            if loan.is_active(sim_month_index):

                interest, principal = loan.monthly_payment()

                # --- 利息支払
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="支払利息",
                    credit_account="預金",
                    amount=interest
                ))

                # --- 元金返済
                self.ledger.add_entries(make_entry_pair(
                    date=d0,
                    debit_account="借入金",
                    credit_account="預金",
                    amount=principal
                ))


        # ============================================================
        # end of monthly entries
        # ============================================================

        return True