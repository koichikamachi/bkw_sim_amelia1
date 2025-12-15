#=========== bkw_sim_amelia1/config/params.py

from dataclasses import dataclass, field
from typing import Optional, List
import datetime

@dataclass
class LoanParams:
    """初期借入金、または追加投資時の借入金のパラメータ"""
    amount: float
    interest_rate: float
    years: int

@dataclass
class ExitParams:
    """物件売却（出口）に関するパラメータ"""
    exit_year: int
    selling_price: float
    selling_cost: float
    income_tax_rate: float

@dataclass
class AdditionalInvestmentParams:
    """追加投資（設備投資など）に関するパラメータ"""
    invest_year: int
    invest_amount: float
    depreciation_years: int
    loan_amount: float
    loan_years: int
    loan_interest_rate: float

@dataclass
class SimulationParams:
    """
    シミュレーション全体で使用される入力パラメータを保持するデータクラス。
    """
    # UIの入力項目に合わせ、全てのパラメータを定義します。
    
    # 1. 取得・初期設定
    property_price_building: float
    property_price_land: float
    brokerage_fee_amount_incl: float
    building_useful_life: int
    building_age: int
    holding_years: int
    initial_loan: Optional[LoanParams]
    initial_equity: float 
    
    # 2. 収益・経費
    rent_setting_mode: str
    target_cap_rate: float
    annual_rent_income_incl: float
    annual_management_fee_initial: float
    repair_cost_annual: float
    insurance_cost_annual: float
    fixed_asset_tax_land: float
    fixed_asset_tax_building: float
    other_management_fee_annual: float

    # UIで計算された管理委託費率（再現表示用）
    management_fee_rate: float 

    # 3. 税金・割合
    consumption_tax_rate: float
    non_taxable_proportion: float
    overdraft_interest_rate: float
    cf_discount_rate: float
    
    # 4. 出口設定
    exit_params: ExitParams
    
    # 5. 追加投資
    additional_investments: List[AdditionalInvestmentParams] = field(default_factory=list)

    # 6. シミュレーション開始日 (UIから一時的に保持)
    start_date: Optional[datetime.date] = field(default=None)

#========= bkw_sim_amelia1/config/params.py end