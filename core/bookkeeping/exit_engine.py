# =======================================
# core/bookkeeping/exit_engine.py
# =======================================

from datetime import date
from core.bookkeeping.journal_entry import JournalEntry, make_entry_pair
from core.tax.tax_utils import TaxUtils


class ExitEngine:
    """
    物件売却（EXIT）時点での全仕訳を作成するエンジン。
    """

    def __init__(self, params, ledger, depreciation_units, loan_units):
        self.p = params
        self.ledger = ledger
        self.dep_units = depreciation_units        # list[DepreciationUnit]
        self.loan_units = loan_units               # list[LoanEngine]
        self.tax = TaxUtils(params.consumption_tax_rate)

    # -------------------------------------------------------------
    # Helper：仕訳追加
    # -------------------------------------------------------------
    def _add(self, entry: JournalEntry):
        self.ledger.add_entry(entry)

    def _add_pair(self, dt, dr, cr, amt):
        for e in make_entry_pair(dt, dr, cr, amt):
            self.ledger.add_entry(e)

    # -------------------------------------------------------------
    # PART 1. 売却収入（税抜 + 仮受消費税）
    # -------------------------------------------------------------
    def _record_sales(self, dt):
        selling_price_incl = self.p.exit_params.selling_price

        # 税抜売却価額と消費税
        ex_tax, vat = self.tax.split_incl_tax(selling_price_incl)

        # 仕訳（預金 / 売却収入・仮受消費税）
        self._add_pair(dt, "預金", "固定資産売却収入", ex_tax)
        self._add_pair(dt, "預金", "仮受消費税", vat)

        return ex_tax, vat

    # -------------------------------------------------------------
    # PART 2. 建物・追加設備の簿価消去（A仕様）
    # -------------------------------------------------------------
    def _record_disposal_cost(self, dt):
        total_cost = 0.0

        # ---- 集計用バッファ ----
        building_book_value = 0.0
        building_accum_depr = 0.0

        additional_book_value = 0.0
        additional_accum_depr = 0.0

        # ------------------------
        # 1) 各 DepreciationUnit を走査
        # ------------------------
        for unit in self.dep_units:
            # 償却済額と簿価を取得
            book_value = unit.get_book_value_at_exit()

            # 累計償却額（＝取得価額 − 簿価）
            accum = unit.acquisition_cost - book_value

            # 分類
            if getattr(unit, "asset_type", "building") == "building":
                building_book_value += book_value
                building_accum_depr += accum
            else:
                additional_book_value += book_value
                additional_accum_depr += accum

        # ---------------------------------------------------------
        # 2) 建物（一本化）
        # ---------------------------------------------------------
        if building_book_value > 0:
            # （借）固定資産売却原価 /（貸）建物
            self._add_pair(dt, "固定資産売却原価", "建物", building_book_value)

            # （借）減価償却累計額（建物） /（貸）固定資産売却原価
            if building_accum_depr > 0:
                self._add_pair(
                    dt,
                    "減価償却累計額（建物）",
                    "固定資産売却原価",
                    building_accum_depr
                )

            total_cost += building_book_value

        # ---------------------------------------------------------
        # 3) 追加設備（完全一本化）
        # ---------------------------------------------------------
        if additional_book_value > 0:
            self._add_pair(dt, "固定資産売却原価", "追加設備", additional_book_value)

            if additional_accum_depr > 0:
                self._add_pair(
                    dt,
                    "減価償却累計額（追加設備）",
                    "固定資産売却原価",
                    additional_accum_depr
                )

            total_cost += additional_book_value

        # ---------------------------------------------------------
        # 4) 土地
        # ---------------------------------------------------------
        land_value = self.p.property_price_land
        if land_value > 0:
            total_cost += land_value
            self._add_pair(dt, "固定資産売却原価", "土地", land_value)

        return total_cost

    # -------------------------------------------------------------
    # PART 3. 売却費用（税抜、控除不能、仮払消費税）
    # -------------------------------------------------------------
    def _record_selling_cost(self, dt):
        selling_cost_incl = self.p.exit_params.selling_cost

        if selling_cost_incl <= 0:
            return 0, 0, 0

        ex_tax, vat = self.tax.split_incl_tax(selling_cost_incl)

        # 按分：課税売上割合
        rate_taxable = 1 - self.p.non_taxable_proportion
        rate_nontaxable = self.p.non_taxable_proportion

        vat_deductible = vat * rate_taxable        # 仮払消費税
        vat_nondeductible = vat * rate_nontaxable  # 控除不能 → 原価算入

        # 税抜売却費用
        self._add_pair(dt, "固定資産売却費用", "預金", ex_tax)

        # 控除不能消費税（費用算入）
        if vat_nondeductible > 0:
            self._add_pair(dt, "固定資産売却費用", "預金", vat_nondeductible)

        # 仮払消費税
        if vat_deductible > 0:
            self._add_pair(dt, "仮払消費税", "預金", vat_deductible)

        return ex_tax, vat_deductible, vat_nondeductible

    # -------------------------------------------------------------
    # PART 4. 消費税の相殺
    # -------------------------------------------------------------
    def _offset_consumption_tax(self, dt):
        """
        仮受消費税 − 仮払消費税 = 納付額（預金で支払い）
        """
        df = self.ledger.get_df()

        vat_received = df[df["account"] == "仮受消費税"]["amount"].sum()
        vat_paid = df[df["account"] == "仮払消費税"]["amount"].sum()
        diff = vat_received - vat_paid

        if diff > 0:
            # 納付
            self._add_pair(dt, "仮受消費税", "預金", diff)

    # -------------------------------------------------------------
    # PART 5. 借入金の完済
    # -------------------------------------------------------------
    def _payoff_loans(self, dt):
        df = self.ledger.get_df()

        for loan in self.loan_units:
            remain = loan.get_remaining_balance()
            if remain > 0:
                self._add_pair(dt, "長期借入金", "預金", remain)

        # 当座借越もゼロにする
        overdraft = df[df["account"] == "当座借越"]["amount"].sum()
        if overdraft > 0:
            self._add_pair(dt, "当座借越", "預金", overdraft)

    # -------------------------------------------------------------
    # PART 6. 法人税（出口時点で一括処理）
    # -------------------------------------------------------------
    def _record_income_tax(self, dt):
        df = self.ledger.get_df()

        # 税引前利益
        pre_tax = df[df["account"] == "税引前当期利益"]["amount"].sum()

        if pre_tax <= 0:
            return 0

        tax = pre_tax * self.p.exit_params.income_tax_rate

        self._add_pair(dt, "法人税等", "未払法人税", tax)
        self._add_pair(dt, "未払法人税", "預金", tax)

        return tax

    # -------------------------------------------------------------
    # MAIN：出口実行
    # -------------------------------------------------------------
    def run(self):
        dt = date(self.p.start_date.year + self.p.exit_params.exit_year, 12, 31)

        # 売却収入
        self._record_sales(dt)

        # 簿価消去
        self._record_disposal_cost(dt)

        # 売却費用
        self._record_selling_cost(dt)

        # 消費税相殺
        self._offset_consumption_tax(dt)

        # 借入完済
        self._payoff_loans(dt)

        # 法人税
        self._record_income_tax(dt)

        return True

# =======================================
# END exit_engine.py
# =======================================