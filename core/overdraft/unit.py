# ===== core/overdraft/unit.py =====

from dataclasses import dataclass

@dataclass
class OverdraftUnit:
    """
    当座借越を管理する「レンガ」。
    ・不足額を自動的に借入
    ・翌月に利息発生
    """

    annual_rate: float            # 例：0.05（5%）
    balance: float = 0.0          # 現在の当座借越残高（元本）

    def apply_month_end(self, cash_balance: float) -> float:
        """
        月末の現金残高を受け取り、不足があれば当座借越に振り替える。
        
        :param cash_balance: 月末現金残高
        :return: 当座借越に振り替えた金額（仕訳生成に使う）
        """
        if cash_balance >= 0:
            return 0.0  # 借り入れ不要

        needed = -cash_balance  # 不足額 = 借入額
        self.balance += needed  # 当座借越残高に追加

        return needed

    def calculate_interest(self) -> float:
        """
        当月の当座借越利息を計算する。
        """
        monthly_rate = self.annual_rate / 12
        return self.balance * monthly_rate

    def repay_if_possible(self, cash_available: float) -> float:
        """
        現金に余裕が出た場合、当座借越を返済する。
        
        :param cash_available: 当月利用可能な現金
        :return: 返済した金額
        """
        if self.balance <= 0:
            return 0.0

        repayment = min(self.balance, cash_available)
        self.balance -= repayment
        return repayment

# ===== end unit.py =====