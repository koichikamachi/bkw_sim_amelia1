# ===== core/depreciation/unit.py =====

from dataclasses import dataclass

@dataclass
class DepreciationUnit:
    """
    固定資産1件を管理するユニット。
    asset_type:
        "building"        → 初期建物
        "additional"      → 追加設備（何回でも可）
    """

    acquisition_cost: float
    useful_life_years: int
    start_year: int
    start_month: int
    asset_type: str = "building"   # "building" or "additional"

    def __post_init__(self):
        # 総償却月数
        self.total_months = self.useful_life_years * 12

        # 月次償却額
        self.monthly_amount = self.acquisition_cost / self.total_months

    # -----------------------------------------
    # 月次減価償却額
    # -----------------------------------------
    def get_monthly_depreciation(self, year: int, month: int) -> float:
        current_index = (year - self.start_year) * 12 + (month - self.start_month) + 1
        if current_index < 1 or current_index > self.total_months:
            return 0.0
        return self.monthly_amount

    # -----------------------------------------
    # 累計減価償却額（指定年月まで）
    # -----------------------------------------
    def get_accumulated_depreciation(self, year: int, month: int) -> float:
        total = 0.0
        for y in range(self.start_year, year + 1):
            for m in range(1, 13):
                if (y == year and m > month):
                    break
                total += self.get_monthly_depreciation(y, m)
        return total

    # -----------------------------------------
    # 残存簿価（指定年月）
    # -----------------------------------------
    def get_book_value(self, year: int, month: int) -> float:
        acc = self.get_accumulated_depreciation(year, month)
        remaining = self.acquisition_cost - acc
        return max(remaining, 0.0)

# ===== end unit.py =====