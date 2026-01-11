# ===== core/loan/unit.py =====

from dataclasses import dataclass
from datetime import date
from typing import Dict

from core.engine.loan_engine import LoanEngine

@dataclass
class LoanUnit:
    """
    LoanEngine を会計シミュレーション用にラップする「レンガ」。
    ・初期借入
    ・追加投資借入
    など、複数 LoanUnit を並列管理可能。
    """

    amount: float                 # 借入金額
    annual_rate: float            # 年利（0.025 = 2.5%）
    years: int                    # 返済年数
    start_year: int               # シミュレーション Year基準
    start_month: int              # 開始月（1〜12）

    def __post_init__(self):
        # 返済計算エンジン
        self.engine = LoanEngine(
            amount=self.amount,
            annual_rate=self.annual_rate,
            years=self.years
        )

    def get_monthly_payment(self, year: int, month: int) -> Dict[str, float]:
        """
        指定された year/month の返済情報を返す。
        Simulation 内の仕訳生成で利用される。
        """

        # シミュレーション開始からの経過月数（1スタート）
        month_index = (year - self.start_year) * 12 + (month - self.start_month) + 1

        if month_index < 1 or month_index > self.engine.total_months:
            # 返済期間外
            return {
                "principal": 0.0,
                "interest": 0.0,
                "total_payment": 0.0,
                "remaining_balance": 0.0
            }

        # LoanEngine の計算結果
        return self.engine.calculate_monthly_payment(month_index)

    def is_active(self, year: int, month: int) -> bool:
        """
        この LoanUnit が指定年月に返済中かどうか。
        """
        month_index = (year - self.start_year) * 12 + (month - self.start_month) + 1
        return 1 <= month_index <= self.engine.total_months

# ===== end unit.py =====