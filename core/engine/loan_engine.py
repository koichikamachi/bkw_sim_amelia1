#==== bkw_sim_amelia1/core/engine/loan_engine.py ====

import math
from typing import Optional, Dict

class LoanEngine:
    """
    以下のコードでは、借入金の元利均等返済の計算ロジックを提供する。
    """
    def __init__(self, amount: float, annual_rate: float, years: int):
        self.initial_amount = amount    # 借入当初残高
        self.annual_rate = annual_rate  # 年利 (例: 0.025 = 2.5%)
        self.years = years              # 返済期間 (年)
        self.total_months = years * 12  # 総返済回数 (月)
        self.monthly_rate = annual_rate / 12.0 # 月利

        # 元利均等返済における月々の均等返済額を計算する
        if self.monthly_rate > 0:
            # 月次返済額 (M) = P * [ i(1 + i)^n / ((1 + i)^n - 1) ]
            # P: 元本, i: 月利, n: 総回数
            numerator = self.monthly_rate * math.pow(1 + self.monthly_rate, self.total_months)
            denominator = math.pow(1 + self.monthly_rate, self.total_months) - 1
            self.monthly_payment = self.initial_amount * (numerator / denominator)
        else:
            # 無利息の場合
            self.monthly_payment = self.initial_amount / self.total_months

    # ★ NEW METHOD: 月次返済額の詳細計算 ★
    def calculate_monthly_payment(self, month_index: int) -> Optional[Dict[str, float]]:
        """
        指定された月 (1から始まる) の返済における元本、利息、残高を計算する。
        """
        if month_index < 1 or month_index > self.total_months:
            return None # 期間外

        # 1. 処理対象月の開始時点のローン残高を求める
        # この計算を簡略化するため、前の月までの残高を再計算する
        current_balance = self.initial_amount
        
        # month_index - 1 の回数だけ、返済をシミュレートして残高を減らす
        for i in range(1, month_index):
            # 前月の利息計算
            interest_paid = current_balance * self.monthly_rate
            
            # 前月の元本返済額
            principal_paid = self.monthly_payment - interest_paid
            
            # 残高を更新 (残高がゼロを下回らないように)
            current_balance = max(0, current_balance - principal_paid)
            
            # 既に完済していたらループを抜ける
            if current_balance <= 0:
                break


        # 2. 当月 (month_index) の計算

        if current_balance <= 0:
            # 既に完済済み
            return {
                'principal': 0.0, 
                'interest': 0.0, 
                'total_payment': 0.0, 
                'remaining_balance': 0.0
            }

        # 当月の利息計算
        interest = current_balance * self.monthly_rate

        # 当月の元本返済額
        principal = self.monthly_payment - interest

        # 最終回調整
        if month_index == self.total_months:
            # 最終回は、残高全額を元本として返済し、利息を調整する
            principal = current_balance
            total_payment = principal + interest
            remaining_balance = 0.0
        else:
            total_payment = self.monthly_payment
            remaining_balance = current_balance - principal

        # 元本がマイナスにならないように調整 (端数処理の都合上)
        if principal < 0:
             principal = 0.0

        return {
            'principal': principal, 
            'interest': interest, 
            'total_payment': total_payment, 
            'remaining_balance': remaining_balance
        }

#======= 以上, core/engine/loan_engine.py end ======