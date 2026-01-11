# ===== core/depreciation/unit.py =====

from dataclasses import dataclass

@dataclass
class DepreciationUnit:
    """
    固定資産1件を管理する「レンガ」。
    ・簿価（税抜）
    ・耐用年数
    ・開始年月（year, month）
    をもち、月次減価償却額を返す。
    """

    acquisition_cost: float              # 取得価額（税抜）
    useful_life_years: int               # 耐用年数（年）
    start_year: int                      # 償却開始年（Year 1基準）
    start_month: int                     # 償却開始月（1〜12）

    def __post_init__(self):
        # 総償却月数を算出
        self.total_months = self.useful_life_years * 12

        # 月次償却額（基本形）
        self.monthly_amount = self.acquisition_cost / self.total_months

    def get_monthly_depreciation(self, year: int, month: int) -> float:
        """
        指定された year/month が、このユニットの償却期間内であれば償却費を返す。
        期間外なら 0。
        """

        # ① シミュレーション開始からの通算月数（1スタート）
        current_index = (year - self.start_year) * 12 + (month - self.start_month) + 1

        # ② 償却期間外はゼロ
        if current_index < 1 or current_index > self.total_months:
            return 0.0

        # ③ 通常月
        # 最終月でズレ調整したい場合はここで後から補正可能
        return self.monthly_amount

    def remaining_value(self, year: int, month: int) -> float:
        """
        指定年月時点での残存簿価を計算する。
        """
        # それまでの償却合計
        total_depr = 0.0
        for y in range(self.start_year, year + 1):
            for m in range(1, 13):
                # 最終ループ条件
                if (y == year and m > month):
                    break
                total_depr += self.get_monthly_depreciation(y, m)

        remaining = self.acquisition_cost - total_depr
        return max(remaining, 0.0)

# ===== end unit.py =====