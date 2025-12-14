#==== bkw_sim_amelia1/core/engine/tax_engine.py ====

class TaxEngine:
    """
    以下のコードでは、月次の課税所得に応じて法人税（所得税）を計算し、
    将来的に消費税の計算にも対応するエンジンを定義している。
    """
    
    # 以下のコードでは、TaxEngineの初期化（実効税率の設定）を定義している
    def __init__(self, corporate_tax_rate: float):
        """
        :param corporate_tax_rate: 法人税等の実効税率 (0.0 ~ 1.0)
        """
        self.tax_rate = corporate_tax_rate
        
    def calculate_tax(self, taxable_income: float) -> float:
        """
        以下のコードでは、課税所得 (収入 - 必要経費 - 減価償却 ± 調整項目) 
        に基づいて法人税（または所得税）を計算している
        
        :param taxable_income: 月次の課税所得
        :return: 月次の法人税額
        """
        # 以下のコードでは、課税所得がマイナス（赤字）の場合は税金をゼロに設定している
        if taxable_income <= 0:
            return 0.0
        
        # 以下のコードでは、法人税額を計算している
        tax_amount = taxable_income * self.tax_rate
        return tax_amount
    
    def calculate_consumption_tax(self, taxable_sales: float, taxable_purchases: float, consumption_tax_rate: float) -> float:
        """
        以下のコードでは、消費税（仮受消費税と仮払消費税の差額）を計算する
        （将来の月次集計に備えてメソッドだけ定義している）
        
        :param taxable_sales: 課税売上（例：建物売却対価、月次家賃の課税分）
        :param taxable_purchases: 課税仕入（例：建物購入、仲介手数料）
        :param consumption_tax_rate: 消費税率
        :return: 納税額（プラスなら未払消費税、マイナスなら還付）
        """
        
        # 以下のコードでは、仮受消費税（ユーザーから受け取った消費税）を計算している
        received_tax = taxable_sales * consumption_tax_rate
        
        # 以下のコードでは、仮払消費税（経費・購入で支払った消費税）を計算している
        paid_tax = taxable_purchases * consumption_tax_rate
        
        # 以下のコードでは、納税額 (仮受 - 仮払) を計算している
        return received_tax - paid_tax

#======= 以上, core/engine/tax_engine.py end ======