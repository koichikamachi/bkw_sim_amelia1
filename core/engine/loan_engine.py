# =======================================
# bkw_sim_amelia1/core/engine/loan_engine.py
# 仕様書 第6章・第2章 LoanParams 準拠版
# =======================================

import math
from typing import Tuple


class LoanUnit:
    """
    仕様書 2.2節 LoanParams に対応する返済計算ユニット。
    ledger.loan_units に登録して使う（DepreciationUnit と同じ設計）。

    対応する返済方式（仕様書名称統一表）：
        "annuity"         → 元利均等返済
        "equal_principal" → 元金均等返済

    外部から呼ぶメソッド：
        is_active(sim_month_index) -> bool
        monthly_payment()          -> (interest: float, principal: float)
        get_remaining_balance()    -> float
    """

    def __init__(
        self,
        amount: float,
        annual_rate: float,
        years: int,
        repayment_method: str = "annuity",
        loan_type: str = "initial",
        start_sim_month: int = 1,
    ):
        """
        Parameters
        ----------
        amount           : 借入元本
        annual_rate      : 年利（例：0.025 = 2.5%）
        years            : 返済期間（年）
        repayment_method : "annuity" or "equal_principal"
        loan_type        : "initial"（初期借入）or "additional"（追加設備借入）
        start_sim_month  : 返済開始シミュレーション月（通算月、1始まり）
        """
        self.initial_amount   = float(amount)
        self.annual_rate      = float(annual_rate)
        self.years            = int(years)
        self.total_months     = years * 12
        self.monthly_rate     = annual_rate / 12.0
        self.repayment_method = repayment_method
        self.loan_type        = loan_type          # "initial" or "additional"
        self.start_sim_month  = start_sim_month

        # 現在の残高（月次returnのたびに更新）
        self._remaining_balance = self.initial_amount

        # 元利均等の場合：固定月次返済額を事前計算
        if repayment_method == "annuity":
            if self.monthly_rate > 0 and self.total_months > 0:
                r = self.monthly_rate
                n = self.total_months
                self._fixed_payment = self.initial_amount * (
                    r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1)
                )
            else:
                self._fixed_payment = (
                    self.initial_amount / self.total_months
                    if self.total_months > 0 else 0.0
                )
        else:
            self._fixed_payment = 0.0  # 元金均等は毎月可変のため不使用

        # 返済済み月数のカウンター
        self._paid_months = 0

    # ------------------------------------------------------------------
    # is_active
    # ------------------------------------------------------------------
    def is_active(self, sim_month_index: int) -> bool:
        """
        指定シミュレーション月に返済が必要かどうか。

        条件：
            - start_sim_month <= sim_month_index
            - まだ total_months 回分の返済が終わっていない
            - 残高 > 0
        """
        if sim_month_index < self.start_sim_month:
            return False
        months_elapsed = sim_month_index - self.start_sim_month + 1
        if months_elapsed > self.total_months:
            return False
        return self._remaining_balance > 0.0

    # ------------------------------------------------------------------
    # monthly_payment
    # ------------------------------------------------------------------
    def monthly_payment(self) -> Tuple[float, float]:
        """
        当月の返済額を計算し、残高を更新する。

        返り値：(interest, principal)
            interest  : 利息
            principal : 元金返済額

        ※ is_active() が True の場合のみ呼ぶこと。
        """
        if self._remaining_balance <= 0.0:
            return 0.0, 0.0

        interest = self._remaining_balance * self.monthly_rate

        if self.repayment_method == "annuity":
            interest, principal = self._annuity_payment(interest)
        else:
            interest, principal = self._equal_principal_payment(interest)

        # 残高更新
        self._remaining_balance = max(0.0, self._remaining_balance - principal)
        self._paid_months += 1

        return round(interest, 0), round(principal, 0)

    def _annuity_payment(self, interest: float) -> Tuple[float, float]:
        """元利均等：固定返済額から利息を引いた残りが元金"""
        principal = self._fixed_payment - interest

        # 最終回調整（端数で残高が残る場合）
        if self._paid_months + 1 == self.total_months:
            principal = self._remaining_balance

        # 元金がマイナスにならないよう保護
        principal = max(0.0, principal)
        return interest, principal

    def _equal_principal_payment(self, interest: float) -> Tuple[float, float]:
        """元金均等：毎月一定の元金 + その月の残高に対する利息"""
        base_principal = self.initial_amount / self.total_months

        # 最終回調整
        if self._paid_months + 1 == self.total_months:
            principal = self._remaining_balance
        else:
            principal = base_principal

        return interest, principal

    # ------------------------------------------------------------------
    # get_remaining_balance
    # ------------------------------------------------------------------
    def get_remaining_balance(self) -> float:
        """現在の借入残高を返す。ExitEngineが参照する。"""
        return self._remaining_balance


# -----------------------------------------------------------------------
# 後方互換：旧コードが LoanEngine を参照している箇所向けのエイリアス
# 新規コードは LoanUnit を使うこと
# -----------------------------------------------------------------------
LoanEngine = LoanUnit

# =======================================
# core/engine/loan_engine.py end
# =======================================