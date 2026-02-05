# ===== core/depreciation/unit.py =====

from dataclasses import dataclass

@dataclass
class DepreciationUnit:
    """
    固定資産1件を管理するユニット。
    asset_type:
        "building"          → 初期建物
        "additional_asset"  → 追加設備（何回でも可）
    """

    acquisition_cost: float
    useful_life_years: int
    start_year: int
    start_month: int
    asset_type: str = "building"   # "building" or "additional_asset"

    def __post_init__(self):
        # 総償却月数
        self.total_months = self.useful_life_years * 12

        # 月次償却額
        self.monthly_amount = self.acquisition_cost / self.total_months

    # -----------------------------------------
    # 月次減価償却額
    # -----------------------------------------
    def get_monthly_depreciation(self, year: int, month: int) -> float:

        # 【修正：この計算式を丸ごと差し替え】
        # 開始年月からの経過月数を計算（0ベース）
        elapsed_months = (year - self.start_year) * 12 + (month - self.start_month)
        
        # 償却期間内かどうかを判定（0〜total_months-1 の間か）
        if 0 <= elapsed_months < self.total_months:
            return self.monthly_amount
        return 0.0        

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