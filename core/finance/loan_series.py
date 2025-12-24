# ==================================================
# bkw_sim_amelia1/core/finance/loan_series.py
# 複数借入対応・年次確定型 LoanSeries
# ==================================================

from dataclasses import dataclass

@dataclass
class LoanSeries:
    """
    単一の借入系列を表す。
    初期借入・追加投資借入の双方に利用可能。
    """
    principal: float
    interest_rate: float
    years: int
    start_year: int

    def annual_principal_payment(self) -> float:
        if self.years <= 0:
            return 0.0
        return self.principal / self.years

    def outstanding_balance(self, year: int) -> float:
        elapsed = year - self.start_year
        if elapsed <= 0:
            return self.principal
        if elapsed >= self.years:
            return 0.0
        return self.principal - self.annual_principal_payment() * elapsed

    def interest_for_year(self, year: int) -> float:
        balance = self.outstanding_balance(year)
        return balance * self.interest_rate

    def principal_payment_for_year(self, year: int) -> float:
        elapsed = year - self.start_year
        if 1 <= elapsed <= self.years:
            return self.annual_principal_payment()
        return 0.0