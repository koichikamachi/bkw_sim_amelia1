#=========== bkw_sim_amelia1/config/params.py ===========

from dataclasses import dataclass, field
from typing import Optional, List
import datetime


# ------------------------------------------------------------
# 借入パラメータ
# ------------------------------------------------------------
@dataclass
class LoanParams:
    amount: float
    interest_rate: float
    years: int


# ------------------------------------------------------------
# EXIT パラメータ
# ------------------------------------------------------------
@dataclass
class ExitParams:
    exit_year: int                     # 売却年（シミュレーション年）
    land_exit_price: float = 0.0       # 土地売却額（非課税）
    building_exit_price: float = 0.0   # 建物売却額（税込）
    exit_cost: float = 0.0             # 売却費用（税込）


# ------------------------------------------------------------
# 追加投資パラメータ（UI と Simulation の橋渡し）
# ------------------------------------------------------------
@dataclass
class AdditionalInvestmentParams:
    # UI(app.py) が渡すフィールド名（絶対に変更しない）
    year: int
    amount: float
    life: int
    loan_amount: float
    loan_years: int
    loan_interest_rate: float

    # ---- Simulation 側が使う標準化プロパティ（読み取り専用）----
    @property
    def invest_year(self):
        return self.year

    @property
    def invest_amount(self):
        return self.amount

    @property
    def depreciation_years(self):
        return self.life


# ------------------------------------------------------------
# シミュレーション全体パラメータ
# ------------------------------------------------------------
@dataclass
class SimulationParams:

    # 取得・初期条件
    property_price_building: float
    property_price_land: float
    brokerage_fee_amount_incl: float
    building_useful_life: int
    building_age: int
    holding_years: int
    initial_loan: Optional[LoanParams]
    initial_equity: float

    # 収益・費用（UI は年次入力 → Simulation は月次換算）
    rent_setting_mode: str
    target_cap_rate: float
    annual_rent_income_incl: float
    annual_management_fee_initial: float
    repair_cost_annual: float
    insurance_cost_annual: float
    fixed_asset_tax_land: float
    fixed_asset_tax_building: float
    other_management_fee_annual: float
    management_fee_rate: float

    # 税率・金融パラメータ
    consumption_tax_rate: float
    non_taxable_proportion: float
    overdraft_interest_rate: float
    cf_discount_rate: float

    # 出口・追加投資
    exit_params: ExitParams
    additional_investments: List[AdditionalInvestmentParams] = field(default_factory=list)

    # 開始日
    start_date: Optional[datetime.date] = None

    # --------------------------------------------------------
    # 月次換算プロパティ（Simulation が直接参照）
    # --------------------------------------------------------
    @property
    def monthly_rent_incl(self):
        return self.annual_rent_income_incl / 12

    @property
    def monthly_admin_cost_incl(self):
        return self.annual_management_fee_initial / 12

    @property
    def monthly_repair_cost_incl(self):
        return self.repair_cost_annual / 12

    @property
    def monthly_insurance_cost(self):
        return self.insurance_cost_annual / 12

    @property
    def monthly_property_tax(self):
        # 土地 + 建物（非課税なので VAT 分離なし）
        return (self.fixed_asset_tax_land + self.fixed_asset_tax_building) / 12

    @property
    def monthly_other_management_cost(self):
        return self.other_management_fee_annual / 12


#=========== END OF FILE ===========