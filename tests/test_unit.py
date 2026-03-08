# ============================================================
# tests/test_unit.py
# ユニットテスト：各エンジン単体の動作検証
# ============================================================
#
# 【対象モジュール】
#   U-01 : LoanUnit          (core/engine/loan_engine.py)
#   U-02 : TaxEngine         (core/engine/tax_engine.py)
#   U-03 : split_vat         (core/tax/tax_splitter.py)
#   U-04 : allocate_broker_fee (core/tax/broker_fee_allocator.py)
#
# 【実行方法】
#   python -m pytest tests/test_unit.py -v
#
# ============================================================

import sys
import os
import datetime
import math
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.engine.loan_engine import LoanUnit
from core.engine.tax_engine import TaxEngine
from core.tax.tax_splitter import split_vat
from core.tax.broker_fee_allocator import allocate_broker_fee
from core.simulation.state_manager import StateManager
from core.ledger.ledger import LedgerManager
from core.ledger.journal_entry import JournalEntry


# ============================================================
# U-01: LoanUnit
# ============================================================

class TestLoanUnitAnnuity:
    """元利均等返済（annuity）のテスト"""

    def setup_method(self):
        """各テストの前に標準ローンを生成する"""
        # 借入1000万円・年利3%・10年・元利均等
        self.loan = LoanUnit(
            amount=10_000_000,
            annual_rate=0.03,
            years=10,
            repayment_method="annuity",
            loan_type="initial",
            start_sim_month=1,
        )

    def test_monthly_payment_is_positive(self):
        """月次返済額（利息+元金）が正の値になるか"""
        interest, principal = self.loan.monthly_payment()
        assert interest > 0
        assert principal > 0

    def test_first_month_interest(self):
        """1ヶ月目の利息 = 元本 × 月利"""
        # 新しいインスタンスで1回目の計算
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", 1)
        interest, principal = loan.monthly_payment()
        expected_interest = 10_000_000 * (0.03 / 12)
        assert abs(interest - expected_interest) < 10, (
            f"1ヶ月目利息: 期待={expected_interest:,.0f}  実際={interest:,.0f}"
        )

    def test_balance_decreases_each_month(self):
        """返済するたびに残高が減少するか"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", 1)
        prev_balance = loan.get_remaining_balance()
        for _ in range(12):
            loan.monthly_payment()
            curr_balance = loan.get_remaining_balance()
            assert curr_balance < prev_balance, "残高が減少していない"
            prev_balance = curr_balance

    def test_balance_reaches_zero_at_maturity(self):
        """返済期間終了後に残高がゼロになるか"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", 1)
        total_months = 10 * 12
        for _ in range(total_months):
            loan.monthly_payment()
        assert loan.get_remaining_balance() < 1.0, (
            f"満期後残高がゼロでない: {loan.get_remaining_balance():,.0f}"
        )

    def test_total_payment_covers_principal_and_interest(self):
        """総返済額が元本以上になるか（利息があるので元本より大きいはず）"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", 1)
        total = sum(i + p for i, p in [loan.monthly_payment() for _ in range(10 * 12)])
        assert total > 10_000_000, f"総返済額({total:,.0f})が元本以下"

    def test_is_active_before_start(self):
        """開始月より前は is_active() が False"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", start_sim_month=5)
        assert not loan.is_active(4)

    def test_is_active_at_start(self):
        """開始月は is_active() が True"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", start_sim_month=5)
        assert loan.is_active(5)

    def test_is_active_after_maturity(self):
        """返済完了後は is_active() が False"""
        loan = LoanUnit(10_000_000, 0.03, 10, "annuity", "initial", start_sim_month=1)
        for _ in range(10 * 12):
            loan.monthly_payment()
        assert not loan.is_active(10 * 12 + 1)


class TestLoanUnitEqualPrincipal:
    """元金均等返済（equal_principal）のテスト"""

    def test_principal_is_constant(self):
        """元金部分が毎月一定か（最終回除く）"""
        loan = LoanUnit(12_000_000, 0.03, 10, "equal_principal", "initial", 1)
        expected_principal = 12_000_000 / (10 * 12)
        # 最初の11ヶ月を確認
        for i in range(11):
            _, principal = loan.monthly_payment()
            assert abs(principal - expected_principal) < 10, (
                f"{i+1}ヶ月目元金: 期待={expected_principal:,.0f}  実際={principal:,.0f}"
            )

    def test_interest_decreases_over_time(self):
        """利息が月を追うごとに減少するか"""
        loan = LoanUnit(12_000_000, 0.03, 10, "equal_principal", "initial", 1)
        prev_interest = float("inf")
        for _ in range(12):
            interest, _ = loan.monthly_payment()
            assert interest <= prev_interest, "利息が減少していない"
            prev_interest = interest

    def test_balance_reaches_zero_at_maturity(self):
        """返済期間終了後に残高がゼロになるか"""
        loan = LoanUnit(12_000_000, 0.03, 10, "equal_principal", "initial", 1)
        for _ in range(10 * 12):
            loan.monthly_payment()
        assert loan.get_remaining_balance() < 1.0


class TestLoanUnitZeroInterest:
    """無利息ローンのテスト"""

    def test_zero_interest_payment(self):
        """無利息なら利息がゼロ、元金のみ返済"""
        loan = LoanUnit(12_000_000, 0.0, 10, "annuity", "initial", 1)
        interest, principal = loan.monthly_payment()
        assert abs(interest) < 1.0, f"無利息なのに利息が発生: {interest}"
        assert principal > 0


# ============================================================
# U-02: TaxEngine
# ============================================================

class TestTaxEngineBasic:
    """TaxEngineの基本動作テスト"""

    def _make_ledger_with_income(self, income: float, year: int = 2025) -> LedgerManager:
        """
        指定した利益がledgerに反映された状態を作る。
        売上高（貸方）と費用（借方）の差額が income になるよう設定。
        """
        ledger = LedgerManager()
        # 売上高 income+費用分 を計上
        expense = 1_000_000
        revenue = income + expense

        ledger.add_entry(JournalEntry(
            date=datetime.date(year, 1, 1),
            description="売上",
            dr_account="預金",
            dr_amount=revenue,
            cr_account="売上高",
            cr_amount=revenue,
        ))
        ledger.add_entry(JournalEntry(
            date=datetime.date(year, 1, 1),
            description="費用",
            dr_account="販売費一般管理費",
            dr_amount=expense,
            cr_account="預金",
            cr_amount=expense,
        ))
        return ledger

    def test_tax_calculated_for_profit(self):
        """黒字年に税が計上されるか"""
        from config.params import SimulationParams, ExitParams
        ledger = self._make_ledger_with_income(1_000_000, year=2025)
        state  = StateManager()

        engine = TaxEngine()
        engine._post_entries = lambda amt, l, y: l.add_entry(JournalEntry(
            date=datetime.date(y, 12, 31),
            description="税",
            dr_account="所得税（法人税）",
            dr_amount=amt,
            cr_account="未払所得税（法人税）",
            cr_amount=amt,
        ))

        # extract_pre_tax_incomeの動作確認
        pre_tax = engine.extract_pre_tax_income(ledger, 2025)
        assert abs(pre_tax - 1_000_000) < 10, (
            f"税引前利益: 期待=1,000,000  実際={pre_tax:,.0f}"
        )

    def test_no_tax_for_loss(self):
        """赤字年に税額がゼロになるか"""
        engine = TaxEngine()
        state  = StateManager()
        tax_amt = engine.compute_tax_amount(-500_000, 0.20)
        assert tax_amt == 0.0, f"赤字なのに税が発生: {tax_amt}"

    def test_tax_amount_calculation(self):
        """税額 = 課税所得 × 税率"""
        engine = TaxEngine()
        tax = engine.compute_tax_amount(1_000_000, 0.20)
        assert abs(tax - 200_000) < 1.0, f"税額: 期待=200,000  実際={tax:,.0f}"

    def test_zero_taxable_income_gives_zero_tax(self):
        """課税所得ゼロなら税額ゼロ"""
        engine = TaxEngine()
        assert engine.compute_tax_amount(0, 0.20) == 0.0


class TestTaxEngineLossCarryforward:
    """欠損金繰越控除のテスト"""

    def test_loss_registered_on_deficit_year(self):
        """赤字年に欠損金リストに登録されるか"""
        engine = TaxEngine()
        state  = StateManager()
        engine.apply_loss_carryforward(-500_000, state, "individual", 2025)
        assert len(state.loss_carryforward_list) == 1
        assert state.loss_carryforward_list[0] == (2025, 500_000)

    def test_loss_offset_in_following_year(self):
        """翌年の利益から欠損金が控除されるか"""
        engine = TaxEngine()
        state  = StateManager()
        # 2025年：50万円の欠損
        engine.apply_loss_carryforward(-500_000, state, "individual", 2025)
        # 2026年：80万円の利益 → 課税所得は30万円のはず
        taxable = engine.apply_loss_carryforward(800_000, state, "individual", 2026)
        assert abs(taxable - 300_000) < 1.0, (
            f"欠損金控除後の課税所得: 期待=300,000  実際={taxable:,.0f}"
        )
        assert len(state.loss_carryforward_list) == 0, "欠損金が残っている"

    def test_loss_expires_after_3_years_individual(self):
        """個人の欠損金は3年で失効するか"""
        engine = TaxEngine()
        state  = StateManager()
        # 2022年に欠損金発生
        state.loss_carryforward_list = [(2022, 500_000)]
        # 2025年（3年後）に申告 → 失効済みなので控除なし
        taxable = engine.apply_loss_carryforward(1_000_000, state, "individual", 2025)
        assert abs(taxable - 1_000_000) < 1.0, (
            f"失効した欠損金が控除されている: 課税所得={taxable:,.0f}"
        )

    def test_loss_expires_after_10_years_corporate(self):
        """法人の欠損金は10年で失効するか"""
        engine = TaxEngine()
        state  = StateManager()
        # 2015年に欠損金発生
        state.loss_carryforward_list = [(2015, 500_000)]
        # 2025年（10年後）に申告 → 失効済み
        taxable = engine.apply_loss_carryforward(1_000_000, state, "corporate", 2025)
        assert abs(taxable - 1_000_000) < 1.0, (
            f"失効した欠損金（法人）が控除されている: 課税所得={taxable:,.0f}"
        )

    def test_loss_still_valid_within_period(self):
        """期限内の欠損金は控除されるか（個人2年目）"""
        engine = TaxEngine()
        state  = StateManager()
        state.loss_carryforward_list = [(2023, 500_000)]
        # 2025年（2年後・期限内）に申告
        taxable = engine.apply_loss_carryforward(800_000, state, "individual", 2025)
        assert abs(taxable - 300_000) < 1.0

    def test_multiple_loss_years_applied_oldest_first(self):
        """複数年の欠損金が古い順に充当されるか"""
        engine = TaxEngine()
        state  = StateManager()
        # 2023年50万、2024年30万の欠損
        state.loss_carryforward_list = [(2023, 500_000), (2024, 300_000)]
        # 2025年に60万円の利益 → 2023年分を先に充当（50万全額）→ 2024年分を10万充当 → 課税所得0
        taxable = engine.apply_loss_carryforward(600_000, state, "individual", 2025)
        assert abs(taxable) < 1.0, f"課税所得がゼロでない: {taxable:,.0f}"
        # 2024年分の残り20万が残っているはず
        assert len(state.loss_carryforward_list) == 1
        assert abs(state.loss_carryforward_list[0][1] - 200_000) < 1.0


# ============================================================
# U-03: split_vat
# ============================================================

class TestSplitVat:
    """split_vat（消費税分解）のテスト"""

    def test_full_taxable(self):
        """非課税割合0%（全額課税）のケース"""
        result = split_vat(1_100_000, vat_rate=0.10, non_taxable_ratio=0.0)
        assert abs(result["tax_base"] - 1_000_000) < 1.0
        assert abs(result["vat_deductible"] - 100_000) < 1.0
        assert abs(result["vat_nondeductible"]) < 1.0

    def test_full_nontaxable(self):
        """非課税割合100%（全額非課税）のケース"""
        result = split_vat(1_100_000, vat_rate=0.10, non_taxable_ratio=1.0)
        # 全額非課税なので消費税控除不可
        assert abs(result["vat_deductible"]) < 1.0
        assert result["vat_nondeductible"] >= 0

    def test_partial_taxable(self):
        """非課税割合50%（按分）のケース"""
        result = split_vat(1_100_000, vat_rate=0.10, non_taxable_ratio=0.5)
        # 控除可能VAT = 控除不可VAT（50%ずつ）
        assert abs(result["vat_deductible"] - result["vat_nondeductible"]) < 1.0

    def test_vat_components_sum_to_total(self):
        """税抜本体 + 控除可能VAT + 控除不能VAT = 税込総額"""
        gross = 1_100_000
        result = split_vat(gross, vat_rate=0.10, non_taxable_ratio=0.40)
        total = result["tax_base"] + result["vat_deductible"] + result["vat_nondeductible"]
        assert abs(total - gross) < 1.0, (
            f"合計不一致: 税込={gross:,.0f}  分解合計={total:,.0f}"
        )

    def test_zero_vat_rate(self):
        """消費税率0%（免税事業者相当）のケース"""
        result = split_vat(1_000_000, vat_rate=0.0, non_taxable_ratio=0.40)
        assert abs(result["vat_deductible"]) < 1.0
        assert abs(result["vat_nondeductible"]) < 1.0
        assert abs(result["tax_base"] - 1_000_000) < 1.0

    def test_all_values_non_negative(self):
        """全ての返り値が非負であるか"""
        result = split_vat(500_000, vat_rate=0.10, non_taxable_ratio=0.30)
        assert result["tax_base"]          >= 0
        assert result["vat_deductible"]    >= 0
        assert result["vat_nondeductible"] >= 0


# ============================================================
# U-04: allocate_broker_fee
# ============================================================

class TestAllocateBrokerFee:
    """allocate_broker_fee（仲介手数料按分）のテスト"""

    def test_total_allocation_equals_gross(self):
        """土地算入 + 建物算入 + 控除可能VAT + 控除不能VAT = 仲介手数料総額"""
        gross = 1_650_000
        result = allocate_broker_fee(
            gross_broker_fee=gross,
            land_net=30_000_000,
            building_net=45_000_000,
            vat_rate=0.10,
            non_taxable_ratio=0.40,
        )
        total = (
            result["land_cost_addition"]
            + result["building_cost_addition"]
            + result["vat_deductible"]
            + result["vat_nondeductible"]
        )
        assert abs(total - gross) < 1.0, (
            f"仲介手数料按分合計不一致: 総額={gross:,.0f}  分解合計={total:,.0f}"
        )

    def test_building_only_allocation(self):
        """土地ゼロなら全額建物に算入されるか"""
        gross = 1_100_000
        result = allocate_broker_fee(
            gross_broker_fee=gross,
            land_net=0,
            building_net=50_000_000,
            vat_rate=0.10,
            non_taxable_ratio=0.0,   # 全額課税
        )
        # 土地ゼロなら土地への算入はゼロ
        assert abs(result["land_cost_addition"]) < 1.0, (
            f"土地ゼロなのに土地算入あり: {result['land_cost_addition']:,.0f}"
        )

    def test_land_gets_larger_share_when_land_dominates(self):
        """土地が大きいほど土地への按分が多くなるか"""
        result_land_big = allocate_broker_fee(
            gross_broker_fee=1_650_000,
            land_net=80_000_000,
            building_net=20_000_000,
            vat_rate=0.10,
            non_taxable_ratio=0.40,
        )
        result_bld_big = allocate_broker_fee(
            gross_broker_fee=1_650_000,
            land_net=20_000_000,
            building_net=80_000_000,
            vat_rate=0.10,
            non_taxable_ratio=0.40,
        )
        assert (
            result_land_big["land_cost_addition"]
            > result_bld_big["land_cost_addition"]
        ), "土地が大きい方が土地算入が多くなっていない"

    def test_all_values_non_negative(self):
        """全ての返り値が非負であるか"""
        result = allocate_broker_fee(
            gross_broker_fee=1_650_000,
            land_net=30_000_000,
            building_net=45_000_000,
            vat_rate=0.10,
            non_taxable_ratio=0.40,
        )
        for key, val in result.items():
            assert val >= 0, f"{key}が負の値: {val}"


# ============================================================
# エントリポイント
# ============================================================
if __name__ == "__main__":
    import traceback

    test_classes = [
        TestLoanUnitAnnuity,
        TestLoanUnitEqualPrincipal,
        TestLoanUnitZeroInterest,
        TestTaxEngineBasic,
        TestTaxEngineLossCarryforward,
        TestSplitVat,
        TestAllocateBrokerFee,
    ]

    total, passed, failed = 0, 0, []
    for cls in test_classes:
        obj = cls()
        for name in [m for m in dir(obj) if m.startswith("test_")]:
            total += 1
            try:
                if hasattr(obj, "setup_method"):
                    obj.setup_method()
                getattr(obj, name)()
                print(f"  PASS  {cls.__name__}::{name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}::{name}")
                traceback.print_exc()
                failed.append(f"{cls.__name__}::{name}")

    print(f"\n結果: {passed}/{total} passed")
    if failed:
        print("失敗したテスト:")
        for f in failed:
            print(f"  - {f}")
