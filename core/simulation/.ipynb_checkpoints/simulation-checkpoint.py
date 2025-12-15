#=========== bkw_sim_amelia1/core/simulation/simulation.py

import datetime
from typing import Optional

# 必要なモジュールをインポート
from bkw_sim_amelia1.config.params import SimulationParams
from bkw_sim_amelia1.core.finance.engine import FinanceEngine 
from bkw_sim_amelia1.core.bookkeeping.ledger import Ledger
from bkw_sim_amelia1.core.bookkeeping.initial_entries import create_initial_entries


class Simulation:
    """
    不動産投資シミュレーション全体を統括するクラス。
    """

    def __init__(self, params: SimulationParams, start_date: datetime.date):
        """
        シミュレーションを初期化します。
        """
        self.params = params
        self.start_date = start_date
        self.ledger = Ledger() # 元帳を初期化

        # FinanceEngineの初期化に引数を渡す
        self.engine = FinanceEngine(
            params=self.params,
            start_date=self.start_date,
            ledger=self.ledger # エンジンに元帳への参照を渡す
        )

    def run(self) -> Ledger:
        """
        シミュレーションを実行し、最終的な元帳を返します。
        """
        
        # 1. 初期仕訳の作成
        create_initial_entries(self.params, self.start_date, self.ledger)

        # 2. 各年度のシミュレーションの実行 (FinanceEngineが担当)
        for year in range(1, self.params.holding_years + 1):
            current_date = self.start_date + datetime.timedelta(days=365 * year)
            self.engine.simulate_annual_operations(year, current_date)

        # 3. 売却仕訳 (Exit) の作成 (最終年のみ)
        if self.params.exit_params.exit_year == self.params.holding_years:
             self.engine.simulate_exit(self.params.holding_years)

        return self.ledger

#========= bkw_sim_amelia1/core/simulation/simulation.py end