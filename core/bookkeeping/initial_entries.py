# ===============================================
# core/bookkeeping/initial_entries.py（完全整合版）
# ===============================================

print("### LOADED initial_entries.py ###")
print("FILE =", __file__)

from datetime import date
from core.tax.tax_utils import TaxUtils
from core.depreciation.unit import DepreciationUnit
from core.engine.loan_engine import LoanEngine
# from core.bookkeeping.journal_entry import make_entry_pair
from core.ledger.journal_entry import make_entry_pair
import os

print(">>>> USING initial_entries.py FROM:", os.path.abspath(__file__))


class InitialEntryGenerator:
    """
    初期投資ブロック（DepreciationUnit / TaxUtils 完全整合版）
    """

    def __init__(self, params, ledger):
        self.p = params
        self.ledger = ledger

        def safe_float(v):
            try:
                return float(str(v).replace(',', ''))
            except:
                return 0.0

        non_taxable = safe_float(getattr(params, "non_taxable_proportion", 0.0))
        taxable_ratio = 1.0 - non_taxable

        self.tax = TaxUtils(
            safe_float(params.consumption_tax_rate),
            taxable_ratio
        )

    # ============================================================
    # 初期投資仕訳の生成
    # ============================================================
    def generate(self, start_date: date):
        p = self.p

        # ------------------------------------------------------------
        # 0. 数値化
        # ------------------------------------------------------------
        bld_price = float(str(p.property_price_building).replace(',', ''))
        land_price = float(str(p.property_price_land).replace(',', ''))
        broker_fee = float(str(p.brokerage_fee_amount_incl).replace(',', ''))

        loan_amt = float(str(getattr(p, "initial_loan_amount", 0)).replace(',', ''))
        loan_rate = float(str(getattr(p, "initial_loan_rate", 0)).replace(',', ''))
        loan_years = int(float(str(getattr(p, "initial_loan_years", 30)).replace(',', '')))

        # ------------------------------------------------------------
        # ① 税抜化
        # ------------------------------------------------------------
        building_net, building_tax = self.tax.split_tax(bld_price)
        land_net = land_price  # 土地は非課税

        # ------------------------------------------------------------
        # ② 仲介手数料（税抜/税込）→ 按分
        # ------------------------------------------------------------
        agent_net, agent_tax = self.tax.split_tax(broker_fee)

        total_price = land_net + building_net
        land_ratio = land_net / total_price if total_price else 0
        bld_ratio = building_net / total_price if total_price else 0

        agent_net_land = agent_net * land_ratio
        agent_net_building = agent_net * bld_ratio

        agent_tax_land = agent_tax * land_ratio
        agent_tax_building = agent_tax * bld_ratio

        # ------------------------------------------------------------
        # ③ 消費税：控除可/不可（allocate_tax は tuple）
        # ------------------------------------------------------------
        bld_tax_deductible, bld_tax_nondeduct = self.tax.allocate_tax(building_tax)
        agt_tax_deductible, agt_tax_nondeduct = self.tax.allocate_tax(agent_tax_building)

        # ------------------------------------------------------------
        # ④ 原価計算
        # ------------------------------------------------------------
        land_cost = land_net + agent_net_land + agent_tax_land

        building_cost = (
            building_net
            + agent_net_building
            + bld_tax_nondeduct
            + agt_tax_nondeduct
        )

        # ------------------------------------------------------------
        # ⑤ 減価償却ユニット（DepreciationUnit 仕様に完全合致）
        # ------------------------------------------------------------
        start_year = start_date.year
        start_month = start_date.month

        depreciation_unit = DepreciationUnit(
            acquisition_cost=building_cost,
            useful_life_years=int(p.building_useful_life),
            start_year=start_year,
            start_month=start_month
        )
        self.ledger.register_depreciation_unit(depreciation_unit)

        # ------------------------------------------------------------
        # ⑥ 借入金 LoanEngine
        # ------------------------------------------------------------
        loan = LoanEngine(
            amount=loan_amt,
            annual_rate=loan_rate,
            years=loan_years
        )
        self.ledger.register_loan_unit(loan)

        # ------------------------------------------------------------
        # ⑦ 仕訳登録
        # ------------------------------------------------------------
        self.ledger.add_entries(make_entry_pair(
            start_date, "土地", "現金", land_cost
        ))

        self.ledger.add_entries(make_entry_pair(
            start_date, "建物", "現金", building_cost
        ))

        if bld_tax_deductible > 0:
            self.ledger.add_entries(make_entry_pair(
                start_date, "仮払消費税", "現金", bld_tax_deductible
            ))

        if agt_tax_deductible > 0:
            self.ledger.add_entries(make_entry_pair(
                start_date, "仮払消費税", "現金", agt_tax_deductible
            ))

        if loan_amt > 0:
            self.ledger.add_entries(make_entry_pair(
                start_date, "現金", "借入金", loan_amt
            ))

        initial_equity = float(str(p.initial_equity).replace(',', ''))
        if initial_equity > 0:
            self.ledger.add_entries(make_entry_pair(
                start_date, "現金", "元入金", initial_equity
            ))

        return {
            "land_cost": land_cost,
            "building_cost": building_cost,
            "building_tax_deductible": bld_tax_deductible,
            "agent_tax_bld_deductible": agt_tax_deductible,
        }

# =============================
# END
# =============================