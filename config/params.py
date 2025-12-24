#=========== bkw_sim_amelia1/config/params.py

from dataclasses import dataclass, field
from typing import Optional, List
import datetime


@dataclass
class LoanParams:
    amount: float
    interest_rate: float
    years: int


@dataclass
class ExitParams:
    exit_year: int
    selling_price: float
    selling_cost: float
    income_tax_rate: float


@dataclass
class AdditionalInvestmentParams:
    invest_year: int
    invest_amount: float
    depreciation_years: int
    loan_amount: float
    loan_years: int
    loan_interest_rate: float


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

    # 収益・費用
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

    # 税率等
    consumption_tax_rate: float
    non_taxable_proportion: float
    overdraft_interest_rate: float
    cf_discount_rate: float

    # 出口・追加投資
    exit_params: ExitParams
    additional_investments: List[AdditionalInvestmentParams] = field(default_factory=list)

    # 開始日
    start_date: Optional[datetime.date] = None

#=========== end params.py