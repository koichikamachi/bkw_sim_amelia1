#==== bkw_sim_amelia1/config/params.py ====

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LoanParams:
    amount: float = 0.0
    interest_rate: float = 0.0
    years: int = 0

@dataclass
class SimulationParams:
    project_name: str = "Default Project"
    # ★ NEW/MODIFIED: 法人税率をUIに追加
    tax_rate_income: float = 0.35 
    
    currency_unit: str = "円" 
    
    consumption_tax_rate: float = 0.10 
    non_taxable_proportion: float = 0.50 
    
    property_price_building: float = 0.0 
    property_price_land: float = 0.0     
    brokerage_fee_amount_incl: float = 0.0 
    
    # 収益
    monthly_rent: float = 0.0          
    
    # ★ NEW: 管理費の内訳を追加
    management_fee_rate: float = 0.0  # 管理委託費率
    annual_management_fee_initial: float = 0.0 # 初年度管理委託費年額
    repair_cost_annual: float = 0.0    # 修繕費（年額）
    insurance_cost_annual: float = 0.0 # 損害保険料（年額）
    fixed_asset_tax_land: float = 0.0  # 固定資産税（土地）
    fixed_asset_tax_building: float = 0.0 # 固定資産税（建物）
    other_management_fee_annual: float = 0.0 # その他管理費（年額）
    
    # ★ NEW: 減価償却関連
    building_useful_life: int = 47 
    building_age: int = 0
    
    initial_loan: Optional[LoanParams] = None
    
    holding_years: int = 0
    
    # ★ NEW/MODIFIED: 出口戦略関連
    exit_fee: float = 0.0
    exit_price_building: float = 0.0
    exit_price_land: float = 0.0

# 以下のコードでは、テスト用のデフォルトパラメータを返す関数を定義している
def get_test_params() -> SimulationParams:
    default_loan = LoanParams(
        amount=70_000_000, 
        interest_rate=0.025, 
        years=30
    )
    
    return SimulationParams(
        project_name="テスト不動産投資",
        tax_rate_income=0.35, 
        
        currency_unit="円",
        
        consumption_tax_rate=0.10, 
        non_taxable_proportion=0.50,
        
        property_price_building=80_000_000, 
        property_price_land=20_000_000,     
        brokerage_fee_amount_incl=3_300_000,
        
        monthly_rent=500_000, 
        
        # 管理費の初期値として年額を仮設定
        annual_management_fee_initial=1_200_000, 
        management_fee_rate=0.00,
        repair_cost_annual=200_000, 
        insurance_cost_annual=50_000, 
        fixed_asset_tax_land=100_000, 
        fixed_asset_tax_building=300_000, 
        other_management_fee_annual=100_000, 
        
        # 減価償却関連
        building_useful_life=47,
        building_age=5,
        
        initial_loan=default_loan,
        
        holding_years=10,
        # 出口戦略関連
        exit_fee=1_000_000, 
        exit_price_building=70_000_000, 
        exit_price_land=30_000_000
    )
#======= 以上, config/params.py end ======