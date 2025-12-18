from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.ledger.ledger import LedgerManager

class InitialEntryGenerator:
    def __init__(self, params: SimulationParams, ledger_manager: LedgerManager):
        """
        物件取得時（Year 0）の開始仕訳を生成する専門クラス。
        params: 入力パラメータ
        ledger_manager: 仕訳を記録するマネージャー
        """
        self.params = params
        self.lm = ledger_manager

    # =============================================================
    # 開始仕訳の一括生成を実行
    # =============================================================
    def generate(self):
        self._record_property_acquisition()
        self._record_loan_execution()

    # =============================================================
    # 1. 物件取得（資産計上）の仕訳
    # 土地、建物、および仲介手数料（土地取得原価に算入）の記録
    # =============================================================
    def _record_property_acquisition(self):
        # 土地の計上
        self.lm.add_entry(0, "土地", "元入金", self.params.property_price_land, "物件購入（土地）")
        
        # 建物の計上
        self.lm.add_entry(0, "初期建物", "元入金", self.params.property_price_building, "物件購入（建物）")
        
        # 仲介手数料の計上（ライムの入力サマリーに基づき、全額土地取得費に算入する仕様）
        if self.params.brokerage_fee_amount_incl > 0:
            self.lm.add_entry(0, "土地", "元入金", self.params.brokerage_fee_amount_incl, "仲介手数料（土地取得原価算入）")

    # =============================================================
    # 2. 資金調達（負債計上）の仕訳
    # 借入金の実行と、それに伴う預金の増加
    # =============================================================
    def _record_loan_execution(self):
        if self.params.initial_loan and self.params.initial_loan.amount > 0:
            loan_amt = self.params.initial_loan.amount
            # 借方：預金 / 貸方：初期投資長期借入金
            self.lm.add_entry(0, "預金", "初期投資長期借入金", loan_amt, "初期借入実行")