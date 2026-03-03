# =======================================
# core/bookkeeping/exit_engine.py（最終完全版）
# =======================================

from datetime import date
from core.bookkeeping.journal_entry import make_entry_pair
from core.tax.tax_utils import TaxUtils


class ExitEngine:
    """
    物件売却（EXIT）処理の完全実装。
    仕様：
      - 土地：非課税
      - 建物：税込 → 税抜＋仮受VAT
      - 追加設備：売却価額ゼロ（建物売却額に内包）
      - 簿価消去はすべて固定資産売却損
      - 累計償却はすべて固定資産売却益に振替
      - 消費税は未払／未収に計上（預金増減は行わない）
      - 所得税は未払計上のみ
    """

    def __init__(self, params, ledger, depreciation_units, loan_units):
        self.p = params
        self.ledger = ledger
        self.dep_units = depreciation_units
        self.loan_units = loan_units
        self.tax = TaxUtils(params.consumption_tax_rate)

    # ============================================================
    # Utility
    # ============================================================
    def _add_pair(self, dt, dr, cr, amt):
        for e in make_entry_pair(dt, dr, cr, amt):
            self.ledger.add_entry(e)

    # ============================================================
    # 1. 売却価額（建物課税・土地非課税）
    # ============================================================
    def _record_sales(self, dt):

        land_price = self.p.exit_params.land_price               # 非課税
        bld_price_incl = self.p.exit_params.building_price       # 税込

        # 建物：税込 → 税抜＋消費税
        bld_ex, vat = self.tax.split_incl_tax(bld_price_incl)

        # 建物（税抜部分）
        if bld_ex > 0:
            self._add_pair(dt, "預金", "固定資産売却益", bld_ex)

        # 建物VAT（仮受）
        if vat > 0:
            self._add_pair(dt, "預金", "仮受消費税", vat)

        # 土地
        if land_price > 0:
            self._add_pair(dt, "預金", "固定資産売却益", land_price)

        return bld_ex, land_price, vat

    # ============================================================
    # 2. 簿価消去（建物・土地・追加設備）
    # ============================================================
    def _record_book_value_disposal(self, dt):

        # まず土地（非減価償却）
        land_acq = self.p.property_price_land
        if land_acq > 0:
            self._add_pair(dt, "固定資産売却損", "土地", land_acq)

        # 次に DepreciationUnit（建物・追加設備）
        for unit in self.dep_units:

            # 売却時点の残簿価
            book = unit.get_book_value(
                dt.year,
                dt.month
            )
            accum = unit.acquisition_cost - book

            # ---- 建物 ----
            if unit.asset_type == "building":

                # 残簿価 → 売却損
                if book > 0:
                    self._add_pair(dt, "固定資産売却損", "建物", book)

                # 累計償却 → 売却益（控除）
                if accum > 0:
                    self._add_pair(dt, "減価償却累計額（建物）", "固定資産売却益", accum)

            # ---- 追加設備（売却価額ゼロ）----
            else:
                # 残簿価 → 全額売却損
                if book > 0:
                    self._add_pair(dt, "固定資産売却損", "追加設備", book)

                # 累計償却 → 売却益
                if accum > 0:
                    self._add_pair(dt, "減価償却累計額（追加設備）", "固定資産売却益", accum)

    # ============================================================
    # 3. 売却費用（控除可能VATは仮払へ、控除不能VATは売却損）
    # ============================================================
    def _record_selling_cost(self, dt):

        cost_incl = self.p.exit_params.selling_cost
        if cost_incl <= 0:
            return

        ex, vat = self.tax.split_incl_tax(cost_incl)

        taxable_ratio = 1 - self.p.non_taxable_proportion
        nondeduct_ratio = self.p.non_taxable_proportion

        vat_deductible = vat * taxable_ratio
        vat_nondeductible = vat * nondeduct_ratio

        # 税抜費用
        self._add_pair(dt, "固定資産売却損", "預金", ex)

        # 控除不能 VAT → 売却損
        if vat_nondeductible > 0:
            self._add_pair(dt, "固定資産売却損", "預金", vat_nondeductible)

        # 控除可能 VAT → 仮払税へ
        if vat_deductible > 0:
            self._add_pair(dt, "仮払消費税", "預金", vat_deductible)

    # ============================================================
    # 4. 消費税の確定額（未払／未収のみ計上）
    # ============================================================
    def _record_consumption_tax_summary(self, dt):

        df = self.ledger.get_df()
        recv = df[df["account"] == "仮受消費税"]["amount"].sum()
        paid = df[df["account"] == "仮払消費税"]["amount"].sum()

        diff = recv - paid

        if diff > 0:
            # 納付額（翌期納付だが今は未払のみ）
            self._add_pair(dt, "仮受消費税", "未払消費税", diff)

        elif diff < 0:
            # 還付額（翌期受取だが今は未収のみ）
            self._add_pair(dt, "未収還付消費税", "仮払消費税", abs(diff))

    # ============================================================
    # 5. 借入金の完済
    # ============================================================
    def _payoff_loans(self, dt):

        for loan in self.loan_units:
            remain = loan.get_remaining_balance()
            if remain > 0:
                self._add_pair(dt, "長期借入金", "預金", remain)

    # ============================================================
    # 6. 所得税（未払のみ）
    # ============================================================
    def _record_income_tax(self, dt):

        df = self.ledger.get_df()
        pre_tax = df[df["account"] == "税引前当期利益"]["amount"].sum()

        if pre_tax <= 0:
            return  # 欠損金 → 将来控除

        tax = pre_tax * self.p.exit_params.income_tax_rate

        self._add_pair(dt, "所得税等", "未払所得税", tax)

    # ============================================================
    # MAIN
    # ============================================================
    def run(self):

        dt = date(self.p.start_date.year + self.p.exit_params.exit_year, 12, 31)

        self._record_sales(dt)
        self._record_book_value_disposal(dt)
        self._record_selling_cost(dt)
        self._record_consumption_tax_summary(dt)
        self._payoff_loans(dt)
        self._record_income_tax(dt)

        return True

# =======================================
# END exit_engine.py
# =======================================