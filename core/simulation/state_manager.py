# ============================================================
# core/simulation/state_manager.py
# ============================================================

class StateManager:
    def __init__(self):
        # シミュレーション月（通算月インデックス、1始まり）
        self.current_month: int = 0

        # 売却済みフラグ
        self.property_sold: bool = False

        # 初期ローン残高（月次更新）
        self.loan_balance: float = 0.0

        # 累積キャッシュフロー
        self.cumulative_cf: float = 0.0

        # 欠損金繰越リスト（仕様書10.3節）
        # 形式：[(発生年: int, 金額: float), ...]  古い順
        self.loss_carryforward_list: list = []

        # デバッグ用ログ
        self.debug: dict = {}

# ============================================================
# core/simulation/state_manager.py end
# ============================================================