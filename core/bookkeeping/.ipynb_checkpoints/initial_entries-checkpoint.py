#=========== bkw_sim_amelia1/core/bookkeeping/initial_entries.py (新規作成)

import datetime
from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.bookkeeping.ledger import Ledger, JournalEntry

def create_initial_entries(params: SimulationParams, purchase_date: datetime.date, ledger: Ledger):
    """
    物件の取得、資金調達に関する初期仕訳を作成し、元帳に登録する。
    
    Args:
        params (SimulationParams): シミュレーションの入力パラメータ。
        purchase_date (datetime.date): 物件の購入日（仕訳日）。
        ledger (Ledger): 仕訳を登録する元帳インスタンス。
    """
    
    # --------------------------------------------------------
    # 1. 資産の取得 (土地、建物、仲介手数料)
    # --------------------------------------------------------
    
    # 【重要】仲介手数料は、土地取得に関する部分は土地に含め、それ以外は経費（雑費/初期費用など）として処理するのが一般的だが、
    # ここでは簡易的に、全額を「土地取得費」として資産計上し、減価償却の対象外とする。
    # ライムの要望に応じて、仲介手数料全額を土地取得費に含める（ただし、後でこの処理は要再検討）。
    
    # 土地取得費 = 土地価格 + 仲介手数料
    land_acquisition_cost = params.property_price_land + params.brokerage_fee_amount_incl
    
    # 建物取得費 = 建物価格
    building_acquisition_cost = params.property_price_building

    # 仕訳の登録 (借方: 資産の増加)
    
    # 建物（借方）
    if building_acquisition_cost > 0:
        ledger.add_entry(JournalEntry(
            date=purchase_date,
            account='初期建物',
            amount=building_acquisition_cost,
            dr_cr='debit',
            description='物件購入 - 建物取得費 (税込)'
        ))
        
    # 土地（借方）
    if land_acquisition_cost > 0:
        ledger.add_entry(JournalEntry(
            date=purchase_date,
            account='土地',
            amount=land_acquisition_cost,
            dr_cr='debit',
            description='物件購入 - 土地取得費及び初期費用（仲介手数料等）'
        ))


    # --------------------------------------------------------
    # 2. 資金調達 (借入金、元入金)
    # --------------------------------------------------------
    
    # 初期借入金（貸方: 負債の増加）
    if params.initial_loan and params.initial_loan.amount > 0:
        loan_amount = params.initial_loan.amount
        ledger.add_entry(JournalEntry(
            date=purchase_date,
            account='初期投資長期借入金',
            amount=loan_amount,
            dr_cr='credit',
            description='初期投資のための長期借入金調達'
        ))
        
    # 元入金（貸方: 資本の増加）
    # 初期投資額 - 借入金 = 元入金
    initial_equity = params.initial_equity
    if initial_equity > 0:
        ledger.add_entry(JournalEntry(
            date=purchase_date,
            account='元入金',
            amount=initial_equity,
            dr_cr='credit',
            description='自己資金（元入金）の投入'
        ))
        
    # --------------------------------------------------------
    # 3. 貸借の検証（現金等の調整）
    # --------------------------------------------------------
    
    # 借方合計（資産）
    debit_total = land_acquisition_cost + building_acquisition_cost
    
    # 貸方合計（負債＋資本）
    credit_total = (params.initial_loan.amount if params.initial_loan else 0) + initial_equity
    
    # 差額（通常、現金/預金で相殺される）
    # 投資総額 = 借入金 + 元入金 となるように計算しているため、
    # 現金残高は初期段階では変動しない（初期投資額と資金調達額が一致する）はずです。
    # 差額はゼロ、つまり現金/預金の変動はなしとして仕訳の登録は行いません。
    # (初期仕訳では、資産 = 負債 + 資本 で貸借一致を維持)

#========= bkw_sim_amelia1/core/bookkeeping/initial_entries.py end