# ============================================================
# core/bookkeeping/monthly_entries.py
# 仕様書 第6章 Monthly Engine 準拠版
# ============================================================
#
# 【責務】
#   毎月の仕訳生成を担当する。
#   自身は計算ロジックを持たず、各ユニット（LoanUnit, DepreciationUnit）
#   に計算を委譲し、結果を ledger に記帳するのみ。
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
#
# 【勘定科目名（仕様書CoA統一表）】
#   管理費        → 販売費一般管理費
#   支払利息      → 長期借入金利息 / 追加設備借入利息（種別で切替）
#   借入金        → 長期借入金 / 追加設備投資借入金（種別で切替）
#   租税公課      → 租税公課（消費税） / 固定資産税（土地）/ 固定資産税（建物）
#
# 【コンストラクタ引数】
#   state 引数は不要（simulation.py は渡さない設計）
#
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
        """
        Parameters
        ----------
        sim_month_index : int
            シミュレーション通算月（1始まり）。
            例：1年目1月 = 1、1年目12月 = 12、2年目1月 = 13
        """
        # シミュレーション月 → カレンダー日付に変換
        d0 = self.map_sim_to_calendar(sim_month_index)

        p = self.p

        # シミュレーション年・月（1始まり）を算出
        # 追加設備の投資年判定に使用する
        sim_year  = (sim_month_index - 1) // 12 + 1
        sim_month = (sim_month_index - 1) % 12 + 1

        # ============================================================
        # 1) 家賃収入（税込 → 税抜 + 仮受消費税）
        #    賃貸収入は課税売上（非課税割合分は消費税なし）。
        #    split_vat により税抜本体と課税売上相当 VAT を分解。
        # ============================================================
        if p.monthly_rent_incl > 0:
            r = split_vat(
                gross_amount=float(p.monthly_rent_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            # 税抜家賃 → 売上高
            self.ledger.add_entries(make_entry_pair(
                d0, "預金", "売上高", r["tax_base"]
            ))
            # 仮受消費税（課税売上分のみ）
            if r["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "預金", "仮受消費税", r["vat_deductible"]
                ))

        # ============================================================
        # 2) 管理費（税込 → 販売費一般管理費 + 仮払消費税）
        #    課税仕入れ。非課税割合分の VAT は控除不能 → 租税公課（消費税）へ。
        # ============================================================
        if p.monthly_admin_cost_incl > 0:
            a = split_vat(
                gross_amount=float(p.monthly_admin_cost_incl),
                vat_rate=self.vat_rate,
                non_taxable_ratio=self.non_taxable_ratio,
            )
            # 税抜管理費 → 販売費一般管理費
            self.ledger.add_entries(make_entry_pair(
                d0, "販売費一般管理費", "預金", a["tax_base"]
            ))
            # 控除可能 VAT → 仮払消費税
            if a["vat_deductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "仮払消費税", "預金", a["vat_deductible"]
                ))
            # 控除不能 VAT → 租税公課（消費税）（費用算入）
            if a["vat_nondeductible"] > 0:
                self.ledger.add_entries(make_entry_pair(
                    d0, "租税公課（消費税）", "預金", a["vat_nondeductible"]
                ))

        # ============================================================
        # 3) 修繕費（税込 → 修繕費 + 仮払消費税）
        #    管理費と同様に VAT を分解する。
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
        # 4) 保険料（非課税・VAT 分離なし）
        #    損害保険料は非課税取引のため、消費税の分解は不要。
        # ============================================================
        if p.monthly_insurance_cost > 0:
            self.ledger.add_entries(make_entry_pair(
                d0, "販売費一般管理費", "預金", float(p.monthly_insurance_cost)
            ))

        # ============================================================
        # 5) その他販管費（税込 → その他販管費 + 仮払消費税）
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
        #    年税額 ÷ 12 で月次按分。土地・建物を別科目で計上する。
        #    ※ 非課税のため VAT 分離なし。
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
        # 7) 追加設備取得（投資年の 1 月のみ処理）
        #
        #    inv.year はシミュレーション年（1始まり）なので sim_year と比較。
        #    月は 1 月固定（仕様書 AdditionalInvestmentParams 設計）。
        #
        #    処理内容：
        #      ① 設備本体（税抜）の取得仕訳
        #      ② 控除可能 VAT → 仮払消費税
        #      ③ 控除不能 VAT → 追加設備（原価算入）
        #      ④ DepreciationUnit 登録
        #      ⑤ 付随借入金がある場合 → 借入金受取仕訳 + LoanUnit 登録
        # ============================================================
        if p.additional_investments:
            for inv in p.additional_investments:

                # 投資年の 1 月のみ処理（月はinv側に持たない設計）
                if inv.year == sim_year and sim_month == 1:

                    gross = float(inv.amount)
                    add_split = split_vat(
                        gross_amount=gross,
                        vat_rate=self.vat_rate,
                        non_taxable_ratio=self.non_taxable_ratio,
                    )
                    add_net    = add_split["tax_base"]
                    add_vat_d  = add_split["vat_deductible"]
                    add_vat_nd = add_split["vat_nondeductible"]

                    # ① 追加設備本体（税抜）
                    self.ledger.add_entries(make_entry_pair(
                        d0, "追加設備", "預金", add_net
                    ))

                    # ② 控除可能 VAT → 仮払消費税
                    if add_vat_d > 0:
                        self.ledger.add_entries(make_entry_pair(
                            d0, "仮払消費税", "預金", add_vat_d
                        ))

                    # ③ 控除不能 VAT → 追加設備（原価算入）
                    #    取得原価に含めることで償却対象額が正確になる
                    if add_vat_nd > 0:
                        self.ledger.add_entries(make_entry_pair(
                            d0, "追加設備", "預金", add_vat_nd
                        ))
                        add_net += add_vat_nd  # 償却対象原価に加算

                    # ④ DepreciationUnit 登録（以降の月次で償却を計算）
                    unit_add = DepreciationUnit(
                        acquisition_cost=add_net,
                        useful_life_years=int(inv.life),
                        start_year=d0.year,
                        start_month=d0.month,
                        asset_type="additional",
                    )
                    self.ledger.register_depreciation_unit(unit_add)

                    # ⑤ 付随借入金（loan_amount > 0 の場合のみ）
                    #    借入金受取仕訳と LoanUnit を登録する。
                    #    科目名：追加設備投資借入金（仕様書CoA統一表）
                    if inv.loan_amount > 0:
                        # 借入金受取仕訳
                        #   借）預金              loan_amount
                        #   貸）追加設備投資借入金 loan_amount
                        self.ledger.add_entries(make_entry_pair(
                            d0, "預金", "追加設備投資借入金", inv.loan_amount
                        ))
                        # LoanUnit 登録（loan_years = 0 の場合は 1 年でフォールバック）
                        loan_add = LoanUnit(
                            amount=inv.loan_amount,
                            annual_rate=inv.loan_interest_rate,
                            years=inv.loan_years if inv.loan_years > 0 else 1,
                            repayment_method="annuity",
                            loan_type="additional",
                            start_sim_month=sim_month_index,
                        )
                        self.ledger.register_loan_unit(loan_add)

        # ============================================================
        # 8) 減価償却（仕様書6.2節）
        #    登録済みの全 DepreciationUnit に対して is_active() を確認し、
        #    当月の償却額を計算して ledger に記帳する。
        #
        #    科目名の対応：
        #      building   → 借）建物減価償却費     ／ 貸）建物減価償却累計額
        #      additional → 借）追加設備減価償却費 ／ 貸）追加設備減価償却累計額
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
        #    登録済みの全 LoanUnit に対して is_active() を確認し、
        #    当月の利息・元金返済額を計算して ledger に記帳する。
        #
        #    科目名はローン種別（loan_type）で切り替える：
        #      initial    → 借）長期借入金利息   ／ 貸）預金
        #                   借）長期借入金        ／ 貸）預金
        #      additional → 借）追加設備借入利息 ／ 貸）預金
        #                   借）追加設備投資借入金／ 貸）預金
        # ============================================================
        for loan in self.ledger.loan_units:
            if loan.is_active(sim_month_index):
                interest, principal = loan.monthly_payment()

                # ローン種別で利息科目・元金科目を切り替える
                if getattr(loan, "loan_type", "initial") == "additional":
                    interest_acct  = "追加設備借入利息"
                    principal_acct = "追加設備投資借入金"
                else:
                    interest_acct  = "長期借入金利息"
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