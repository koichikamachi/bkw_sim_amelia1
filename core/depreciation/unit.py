# =======================================
# core/depreciation/unit.py
# =======================================

from dataclasses import dataclass, field


@dataclass
class DepreciationUnit:
    """
    固定資産1件を管理するユニット。

    asset_type:
        "building"   → 初期建物
        "additional" → 追加設備（複数可）
    """
    acquisition_cost: float
    useful_life_years: int
    start_year: int
    start_month: int
    asset_type: str = "building"   # "building" or "additional"

    def __post_init__(self):
        self.total_months    = self.useful_life_years * 12
        self._monthly_amount = self.acquisition_cost / self.total_months

    # -----------------------------------------
    # is_active：償却期間内かどうか
    # monthly_entries.py が呼ぶ
    # -----------------------------------------
    def is_active(self, year: int, month: int) -> bool:
        elapsed = (year - self.start_year) * 12 + (month - self.start_month)
        return 0 <= elapsed < self.total_months

    # -----------------------------------------
    # monthly_amount()：月次償却額を返すメソッド
    # monthly_entries.py が unit.monthly_amount() と呼ぶ
    # -----------------------------------------
    def monthly_amount(self) -> float:
        return self._monthly_amount

    # -----------------------------------------
    # get_monthly_depreciation：年月指定版（exit_engine等が使用）
    # -----------------------------------------
    def get_monthly_depreciation(self, year: int, month: int) -> float:
        if self.is_active(year, month):
            return self._monthly_amount
        return 0.0

    # -----------------------------------------
    # 累計減価償却額（指定年月まで）
    # -----------------------------------------
    def get_accumulated_depreciation(self, year: int, month: int) -> float:
        elapsed = (year - self.start_year) * 12 + (month - self.start_month)
        # 償却期間内の経過月数（超えたら total_months で打ち切り）
        active_months = max(0, min(elapsed + 1, self.total_months))
        return self._monthly_amount * active_months

    # -----------------------------------------
    # 残存簿価（指定年月）
    # -----------------------------------------
    def get_book_value(self, year: int, month: int) -> float:
        acc = self.get_accumulated_depreciation(year, month)
        return max(self.acquisition_cost - acc, 0.0)

# ===== end unit.py =====