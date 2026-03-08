# ============================================================
# tests/test_integration_minimal.py
# 統合テスト：最小構成（借入なし・追加設備なし・3年保有）
# ============================================================
#
# 【テスト方針】
#   Streamlit を一切使わず、SimulationParams を直接組み立てて
#   Simulation.run() を実行し、ledger の数値を検証する。
#
# 【最小構成の定義】
#   - 建物取得あり（土地あり）
#   - 仲介手数料あり
#   - 借入なし（全額自己資金）
#   - 追加設備なし
#   - 保有3年・3年目にExit
#   - 個人課税・消費税率10%・非課税割合40%
#
# 【検証項目】
#   T-01 : 全年度で借方合計 = 貸方合計（貸借一致）
#   T-02 : 全年度でBS 資産合計 = 負債・純資産合計
#   T-03 : 消費税精算後に仮払消費税・仮受消費税の残高がゼロ
#   T-04 : Exit年に建物・土地・追加設備の残高がゼロ
#   T-05 : Exit年最終精算後のBSが
#           「預金・元入金・繰越利益剰余金」に収束している
#
# 【実行方法】
#   プロジェクトルートで: pytest tests/test_integration_minimal.py -v
#
# ============================================================

import sys
import os
import datetime
import pytest

# プロジェクトルートを sys.path に追加（プロジェクトルートから実行する前提）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.params import (
    SimulationParams,
    LoanParams,
    ExitParams,
    AdditionalInvestmentParams,
)
from core.simulation.simulation import Simulation


# ============================================================
# テスト用パラメータ生成ヘルパー
# ============================================================

def make_minimal_params(
    holding_years: int = 3,
    exit_year: int = 3,
    with_loan: bool = False,
    loan_amount: float = 30_000_000,
    loan_years: int = 20,
    loan_rate: float = 0.025,
    land_price: float = 30_000_000,
    building_price_incl: float = 50_000_000,   # 税込
    broker_fee_incl: float = 1_650_000,          # 税込
    land_exit_price: float = 30_000_000,
    building_exit_price_incl: float = 30_000_000,
    exit_cost_incl: float = 1_000_000,
    entity_type: str = "individual",
    income_tax_rate: float = 0.20,
    annual_rent_incl: float = 2_400_000,
    non_taxable_proportion: float = 0.40,
) -> SimulationParams:
    """
    テスト用 SimulationParams を生成する。
    デフォルトは最小構成（借入なし・追加設備なし・3年保有）。
    """
    initial_loan = None
    if with_loan:
        initial_loan = LoanParams(
            amount=loan_amount,
            interest_rate=loan_rate,
            years=loan_years,
            repayment_method="annuity",
        )

    # 自己資金 = 取得コスト合計（税込）
    # 借入がある場合は差額のみ自己資金
    total_cost = land_price + building_price_incl + broker_fee_incl
    initial_equity = total_cost - (loan_amount if with_loan else 0)

    return SimulationParams(
        # 取得
        property_price_building=building_price_incl,
        property_price_land=land_price,
        brokerage_fee_amount_incl=broker_fee_incl,
        building_useful_life=22,
        building_age=5,
        holding_years=holding_years,
        initial_loan=initial_loan,
        initial_equity=initial_equity,
        # 収益・費用（年次）
        rent_setting_mode="manual",
        target_cap_rate=0.05,
        annual_rent_income_incl=annual_rent_incl,
        annual_management_fee_initial=240_000,
        repair_cost_annual=120_000,
        insurance_cost_annual=60_000,
        fixed_asset_tax_land=80_000,
        fixed_asset_tax_building=120_000,
        other_management_fee_annual=0,
        management_fee_rate=0.05,
        # 税率
        consumption_tax_rate=0.10,
        non_taxable_proportion=non_taxable_proportion,
        overdraft_interest_rate=0.02,
        cf_discount_rate=0.05,
        # Exit
        exit_params=ExitParams(
            exit_year=exit_year,
            land_exit_price=land_exit_price,
            building_exit_price=building_exit_price_incl,
            exit_cost=exit_cost_incl,
        ),
        additional_investments=[],
        start_date=datetime.date(2025, 1, 1),
        entity_type=entity_type,
        income_tax_rate=income_tax_rate,
        corporate_tax_rate=0.30,
    )


def run_simulation(params: SimulationParams) -> "LedgerManager":
    """シミュレーションを実行してledgerを返すヘルパー"""
    sim = Simulation(params, params.start_date)
    sim.run()
    return sim.ledger


# ============================================================
# T-01: 全期間で借方合計 = 貸方合計（貸借一致）
# ============================================================

class TestBalanceEquality:
    """T-01: 全仕訳の借方合計と貸方合計が一致するか"""

    def test_debit_equals_credit_minimal(self):
        """最小構成（借入なし）で貸借が合うか"""
        params = make_minimal_params()
        ledger = run_simulation(params)
        df = ledger.get_df()

        debit_total  = df[df["dr_cr"] == "debit" ]["amount"].sum()
        credit_total = df[df["dr_cr"] == "credit"]["amount"].sum()
        diff = abs(debit_total - credit_total)

        assert diff < 1.0, (
            f"貸借不一致: 借方合計={debit_total:,.0f}  貸方合計={credit_total:,.0f}  "
            f"差額={diff:,.0f}"
        )

    def test_debit_equals_credit_with_loan(self):
        """借入ありで貸借が合うか"""
        params = make_minimal_params(with_loan=True)
        ledger = run_simulation(params)
        df = ledger.get_df()

        debit_total  = df[df["dr_cr"] == "debit" ]["amount"].sum()
        credit_total = df[df["dr_cr"] == "credit"]["amount"].sum()
        diff = abs(debit_total - credit_total)

        assert diff < 1.0, (
            f"貸借不一致（借入あり）: 差額={diff:,.0f}"
        )

    def test_debit_equals_credit_each_year(self):
        """年度ごとに貸借が合うか（累積ではなく当期分のみ）"""
        params = make_minimal_params()
        ledger = run_simulation(params)
        df = ledger.get_df()

        for year in sorted(df["year"].unique()):
            ydf = df[df["year"] == year]
            debit  = ydf[ydf["dr_cr"] == "debit" ]["amount"].sum()
            credit = ydf[ydf["dr_cr"] == "credit"]["amount"].sum()
            diff   = abs(debit - credit)
            assert diff < 1.0, (
                f"{year}年度 貸借不一致: 借方={debit:,.0f}  貸方={credit:,.0f}  差額={diff:,.0f}"
            )


# ============================================================
# T-02: BS 資産合計 = 負債・純資産合計
# ============================================================

class TestBSEquality:
    """T-02: BSの資産合計と負債・純資産合計が一致するか"""

    @staticmethod
    def _asset_balance(df, account: str) -> float:
        """資産科目の借方残（dr - cr）"""
        dr = df[df["account"] == account][df["dr_cr"] == "debit" ]["amount"].sum()
        cr = df[df["account"] == account][df["dr_cr"] == "credit"]["amount"].sum()
        return float(dr - cr)

    @staticmethod
    def _liab_balance(df, account: str) -> float:
        """負債・純資産科目の貸方残（cr - dr）"""
        dr = df[df["account"] == account][df["dr_cr"] == "debit" ]["amount"].sum()
        cr = df[df["account"] == account][df["dr_cr"] == "credit"]["amount"].sum()
        return float(cr - dr)

    def test_bs_balanced_each_year(self):
        """各年度末時点のBS資産合計と負債・純資産合計が一致するか"""
        params = make_minimal_params()
        ledger = run_simulation(params)
        df_all = ledger.get_df()
        years  = sorted(df_all["year"].unique())

        # PL累積利益（当期利益の累積 = 繰越利益剰余金）を年度別に計算
        pl_profit = {}
        cumulative = 0.0
        for y in years:
            ydf = df_all[df_all["year"] == y]
            # 売上高（貸方）- 費用合計（借方）で当期利益を近似
            # ※ fs_builder と同じロジックは重複するため、
            #   ここでは直接 繰越利益剰余金 の仕訳残高から取得する
            pass

        for y in years:
            # 当期までの累積仕訳
            cum_df = df_all[df_all["year"] <= y]

            def a(acc): return self._asset_balance(cum_df, acc)
            def l(acc): return self._liab_balance(cum_df, acc)

            # 資産合計
            bld_dep = float(
                cum_df[(cum_df["account"] == "建物減価償却累計額") & (cum_df["dr_cr"] == "credit")]["amount"].sum()
                - cum_df[(cum_df["account"] == "建物減価償却累計額") & (cum_df["dr_cr"] == "debit" )]["amount"].sum()
            )
            add_dep = float(
                cum_df[(cum_df["account"] == "追加設備減価償却累計額") & (cum_df["dr_cr"] == "credit")]["amount"].sum()
                - cum_df[(cum_df["account"] == "追加設備減価償却累計額") & (cum_df["dr_cr"] == "debit" )]["amount"].sum()
            )

            asset_total = (
                a("預金")
                + a("未収還付消費税")
                + a("仮払消費税")
                + a("建物")  - bld_dep
                + a("追加設備") - add_dep
                + a("土地")
            )

            # 負債・純資産合計
            # 繰越利益剰余金はPLの貸借差額から計算
            pl_accounts_credit = [
                "売上高", "固定資産売却益（損）"
            ]
            pl_accounts_debit = [
                "建物減価償却費", "追加設備減価償却費",
                "修繕費", "その他販管費", "販売費一般管理費",
                "租税公課（消費税）", "固定資産税（土地）", "固定資産税（建物）",
                "長期借入金利息", "追加設備借入利息", "当座借越利息",
                "所得税（法人税）",
            ]
            BS_ACCOUNTS = {
                "預金","建物","土地","追加設備",
                "建物減価償却累計額","追加設備減価償却累計額",
                "仮払消費税","仮受消費税","未払消費税","未収還付消費税",
                "長期借入金","追加設備投資借入金","当座借越借入金",
                "元入金","繰越利益剰余金",
                "未払所得税（法人税）","固定資産売却仮勘定",
            }
            pl_df = cum_df[~cum_df["account"].isin(BS_ACCOUNTS)]
            retained_earnings = float(
                pl_df[pl_df["dr_cr"] == "credit"]["amount"].sum()
                - pl_df[pl_df["dr_cr"] == "debit" ]["amount"].sum()
            )

            liab_total = (
                l("未払消費税")
                + l("未払所得税（法人税）")
                + l("当座借越借入金")
                + l("長期借入金")
                + l("追加設備投資借入金")
                + l("元入金")
                + retained_earnings
            )

            diff = abs(asset_total - liab_total)
            assert diff < 1.0, (
                f"{y}年度末 BS不一致: "
                f"資産合計={asset_total:,.0f}  "
                f"負債・純資産合計={liab_total:,.0f}  "
                f"差額={diff:,.0f}"
            )


# ============================================================
# T-03: 消費税精算後の仮払・仮受残高がゼロ
# ============================================================

class TestVATSettlement:
    """T-03: 各年度末に仮払消費税・仮受消費税が精算されているか"""

    def test_vat_cleared_after_year_end(self):
        """
        各年度の仕訳全体で、仮払消費税・仮受消費税の残高が
        年末精算仕訳によりゼロになっているか。
        """
        params = make_minimal_params()
        ledger = run_simulation(params)
        df_all = ledger.get_df()
        years  = sorted(df_all["year"].unique())

        for y in years:
            cum_df = df_all[df_all["year"] <= y]

            # 仮払消費税残高（借方残）
            paid_dr = cum_df[(cum_df["account"] == "仮払消費税") & (cum_df["dr_cr"] == "debit" )]["amount"].sum()
            paid_cr = cum_df[(cum_df["account"] == "仮払消費税") & (cum_df["dr_cr"] == "credit")]["amount"].sum()
            paid_balance = paid_dr - paid_cr

            # 仮受消費税残高（貸方残）
            recv_cr = cum_df[(cum_df["account"] == "仮受消費税") & (cum_df["dr_cr"] == "credit")]["amount"].sum()
            recv_dr = cum_df[(cum_df["account"] == "仮受消費税") & (cum_df["dr_cr"] == "debit" )]["amount"].sum()
            recv_balance = recv_cr - recv_dr

            assert abs(paid_balance) < 1.0, (
                f"{y}年度末: 仮払消費税が残っている（残高={paid_balance:,.0f}）"
            )
            assert abs(recv_balance) < 1.0, (
                f"{y}年度末: 仮受消費税が残っている（残高={recv_balance:,.0f}）"
            )


# ============================================================
# T-04: Exit年に固定資産残高がゼロ
# ============================================================

class TestExitAssetClearance:
    """T-04: Exit年末に建物・土地・追加設備の残高がゼロになっているか"""

    def test_fixed_assets_cleared_on_exit(self):
        """Exit年末に固定資産の帳簿価額がゼロになるか"""
        params  = make_minimal_params(exit_year=3)
        ledger  = run_simulation(params)
        df_all  = ledger.get_df()
        exit_cal_year = params.start_date.year + params.exit_params.exit_year - 1

        # Exit年までの累積
        cum_df = df_all[df_all["year"] <= exit_cal_year]

        def net_asset(acc):
            dr = cum_df[(cum_df["account"] == acc) & (cum_df["dr_cr"] == "debit" )]["amount"].sum()
            cr = cum_df[(cum_df["account"] == acc) & (cum_df["dr_cr"] == "credit")]["amount"].sum()
            return float(dr - cr)

        bld_net = net_asset("建物")
        land_net = net_asset("土地")

        assert abs(bld_net) < 1.0, (
            f"Exit年末: 建物残高がゼロでない（残高={bld_net:,.0f}）"
        )
        assert abs(land_net) < 1.0, (
            f"Exit年末: 土地残高がゼロでない（残高={land_net:,.0f}）"
        )


# ============================================================
# T-05: 最終精算後のBS構成
# ============================================================

class TestFinalBalanceSheet:
    """T-05: Exit年最終精算後のBSが所定の科目のみになっているか"""

    # 最終BSに残るべき科目（仕様書9.2節ステップ8）
    EXPECTED_REMAINING = {"預金", "元入金", "繰越利益剰余金"}

    # 最終BSにゼロ以外で残ってはいけない科目
    SHOULD_BE_ZERO = {
        "当座借越借入金",
        "未払消費税",
        "未収還付消費税",
        "未払所得税（法人税）",
        "仮払消費税",
        "仮受消費税",
        "固定資産売却仮勘定",
        "建物",
        "土地",
        "追加設備",
        "長期借入金",
        "追加設備投資借入金",
    }

    def test_liability_cleared_after_final_settlement(self):
        """最終精算後に当座借越・未払消費税・未払所得税がゼロになるか"""
        params  = make_minimal_params(exit_year=3)
        ledger  = run_simulation(params)
        df_all  = ledger.get_df()
        exit_cal_year = params.start_date.year + params.exit_params.exit_year - 1
        cum_df  = df_all[df_all["year"] <= exit_cal_year]

        for acc in self.SHOULD_BE_ZERO:
            dr = float(cum_df[(cum_df["account"] == acc) & (cum_df["dr_cr"] == "debit" )]["amount"].sum())
            cr = float(cum_df[(cum_df["account"] == acc) & (cum_df["dr_cr"] == "credit")]["amount"].sum())
            balance = abs(dr - cr)
            assert balance < 1.0, (
                f"最終精算後: {acc}が残っている（残高={dr-cr:,.0f}）"
            )


# ============================================================
# T-06: 仲介手数料なしケースとの比較
# ============================================================

class TestBrokerFee:
    """T-06: 仲介手数料の有無で建物取得原価が変わるか"""

    def test_building_cost_higher_with_broker_fee(self):
        """
        仲介手数料ありの場合、建物の取得原価（借方累積）が
        なしの場合より大きくなるか（仲介手数料の建物算入分）
        """
        params_with    = make_minimal_params(broker_fee_incl=1_650_000)
        params_without = make_minimal_params(broker_fee_incl=0)

        ledger_with    = run_simulation(params_with)
        ledger_without = run_simulation(params_without)

        df_with    = ledger_with.get_df()
        df_without = ledger_without.get_df()

        bld_with = float(
            df_with[(df_with["account"] == "建物") & (df_with["dr_cr"] == "debit")]["amount"].sum()
        )
        bld_without = float(
            df_without[(df_without["account"] == "建物") & (df_without["dr_cr"] == "debit")]["amount"].sum()
        )

        assert bld_with > bld_without, (
            f"仲介手数料あり({bld_with:,.0f}) が なし({bld_without:,.0f}) 以下になっている"
        )

    def test_land_cost_higher_with_broker_fee(self):
        """土地についても仲介手数料あり > なし"""
        params_with    = make_minimal_params(broker_fee_incl=1_650_000)
        params_without = make_minimal_params(broker_fee_incl=0)

        ledger_with    = run_simulation(params_with)
        ledger_without = run_simulation(params_without)

        df_with    = ledger_with.get_df()
        df_without = ledger_without.get_df()

        land_with = float(
            df_with[(df_with["account"] == "土地") & (df_with["dr_cr"] == "debit")]["amount"].sum()
        )
        land_without = float(
            df_without[(df_without["account"] == "土地") & (df_without["dr_cr"] == "debit")]["amount"].sum()
        )

        assert land_with > land_without, (
            f"土地：仲介手数料あり({land_with:,.0f}) が なし({land_without:,.0f}) 以下になっている"
        )


# ============================================================
# T-07: 土地のみ取得（建物ゼロ）
# ============================================================

class TestLandOnly:
    """T-07: 建物ゼロのケースで貸借が合い、償却が発生しないか"""

    def test_no_depreciation_when_building_is_zero(self):
        """建物ゼロなら建物減価償却費の仕訳が存在しない"""
        params = make_minimal_params(building_price_incl=0, broker_fee_incl=0)
        ledger = run_simulation(params)
        df     = ledger.get_df()

        dep_entries = df[df["account"] == "建物減価償却費"]
        assert len(dep_entries) == 0, (
            f"建物ゼロなのに建物減価償却費が計上されている（{len(dep_entries)}件）"
        )

    def test_balance_land_only(self):
        """建物ゼロでも貸借が合うか"""
        params = make_minimal_params(building_price_incl=0, broker_fee_incl=0)
        ledger = run_simulation(params)
        df     = ledger.get_df()

        dr = df[df["dr_cr"] == "debit" ]["amount"].sum()
        cr = df[df["dr_cr"] == "credit"]["amount"].sum()
        assert abs(dr - cr) < 1.0, f"土地のみ構成で貸借不一致: 差額={abs(dr-cr):,.0f}"


# ============================================================
# T-08: 建物のみ取得（土地ゼロ）
# ============================================================

class TestBuildingOnly:
    """T-08: 土地ゼロのケースで貸借が合い、土地仕訳が存在しないか"""

    def test_no_land_entry_when_land_is_zero(self):
        """土地ゼロなら土地の仕訳が存在しない"""
        params = make_minimal_params(
            land_price=0,
            land_exit_price=0,
            broker_fee_incl=0,   # 土地ゼロの場合、按分計算を単純化するため0に
        )
        ledger = run_simulation(params)
        df     = ledger.get_df()

        land_entries = df[df["account"] == "土地"]
        assert len(land_entries) == 0, (
            f"土地ゼロなのに土地の仕訳が存在する（{len(land_entries)}件）"
        )

    def test_balance_building_only(self):
        """土地ゼロでも貸借が合うか"""
        params = make_minimal_params(land_price=0, land_exit_price=0, broker_fee_incl=0)
        ledger = run_simulation(params)
        df     = ledger.get_df()

        dr = df[df["dr_cr"] == "debit" ]["amount"].sum()
        cr = df[df["dr_cr"] == "credit"]["amount"].sum()
        assert abs(dr - cr) < 1.0, f"建物のみ構成で貸借不一致: 差額={abs(dr-cr):,.0f}"


# ============================================================
# エントリポイント（pytest 以外から直接実行する場合）
# ============================================================
if __name__ == "__main__":
    import traceback

    test_classes = [
        TestBalanceEquality,
        TestBSEquality,
        TestVATSettlement,
        TestExitAssetClearance,
        TestFinalBalanceSheet,
        TestBrokerFee,
        TestLandOnly,
        TestBuildingOnly,
    ]

    total, passed, failed = 0, 0, []
    for cls in test_classes:
        obj = cls()
        for name in [m for m in dir(obj) if m.startswith("test_")]:
            total += 1
            try:
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
