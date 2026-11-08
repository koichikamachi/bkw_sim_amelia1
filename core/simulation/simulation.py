# ===============================
# core/simulation/simulation.py
# 仕様書 第4章・0.7節 シミュレーション制御フロー 準拠版
# ===============================
#
# 【責務】
#   SimulationControllerとして全エンジンの実行順序を管理する。
#   各エンジンは自律的に仕訳を生成し、本クラスは調整役に徹する。
#
# 【処理順序（仕様書0.7節 絶対厳守）】
#   Phase 1 : 取得フェーズ（InitialEntryGenerator）
#   Phase 2 : 月次フェーズ × 12ヶ月（MonthlyEntryGenerator）
#             2月は前年の税金を預金から納付（TaxEngine.settle_tax_balances）
#             毎月、当座借越の利息 → 月末の借入・返済（OverdraftEngine）
#   Phase 3 : Exit フェーズ（ExitEngine）← Exit年のみ、月次完了後
#   Phase 4 : 消費税精算（YearEndEntryGenerator）
#   Phase 5 : 税計算（TaxEngine）
#   Phase 6 : Exit年のみ、Tax後
#             6a 出口の年の税金を預金から納付
#             6b 当座借越の一括返済（不足は元入金で補填）
#             6c 最終精算（ExitEngine.post_final_settlement_entries、通常は仕訳なし）
#   売却の年でループを終える（原型 Excel 版 FST-R b03.7 準拠）
#
# 【重要：calendar_year について】
#   ledger.get_df() の year 列はカレンダー年（例：2025, 2026, 2027）。
#   year_end_entries / tax_engine は ledger.year と突き合わせてフィルタするため、
#   sim_year（1, 2, 3...）ではなく calendar_year（2025, 2026, 2027...）を渡す。
#   calendar_year = start_date.year + sim_year - 1
#
# ===============================

from datetime import date

from config.params import SimulationParams
from core.ledger.ledger import LedgerManager
from core.bookkeeping.initial_entries import InitialEntryGenerator
from core.bookkeeping.monthly_entries import MonthlyEntryGenerator
from core.bookkeeping.year_end_entries import YearEndEntryGenerator
from core.engine.exit_engine import ExitEngine
from core.engine.tax_engine import TaxEngine
from core.engine.overdraft_engine import OverdraftEngine
from core.simulation.state_manager import StateManager


class Simulation:
    """
    仕様書 第4章 SimulationController

    全エンジンのオーケストレーションを担当する。
    自身は仕訳を一切生成しない。
    """

    def __init__(self, params: SimulationParams, start_date: date):
        self.params     = params
        self.start_date = start_date
        self.ledger     = LedgerManager()
        self.state      = StateManager()

    # --------------------------------------------------------
    # カレンダーマッパー
    # シミュレーション通算月（1始まり）→ 実カレンダー日付
    # 例：start_date = 2025-01-01, sim_month_index = 13 → 2026-01-01
    # --------------------------------------------------------
    def map_sim_to_calendar(self, sim_month_index: int) -> date:
        idx   = sim_month_index - 1
        year  = self.start_date.year + (idx // 12)
        month = ((self.start_date.month - 1) + (idx % 12)) % 12 + 1
        return date(year, month, 1)

    # --------------------------------------------------------
    # メインエントリポイント
    # --------------------------------------------------------
    def run(self) -> None:

        # ==================================================
        # Phase 1: 取得フェーズ
        #   土地・建物・仲介手数料の仕訳生成と
        #   DepreciationUnit / LoanUnit の登録を行う。
        # ==================================================
        init = InitialEntryGenerator(self.params, self.ledger)
        init.generate(self.start_date)

        # ==================================================
        # Phase 2以降で使うエンジンをあらかじめ生成しておく
        # ==================================================
        monthly    = MonthlyEntryGenerator(
            params=self.params,
            ledger=self.ledger,
            calendar_mapper=self.map_sim_to_calendar,
        )
        year_end   = YearEndEntryGenerator(
            params=self.params,
            ledger=self.ledger,
            start_year=self.start_date.year,
        )
        tax_engine = TaxEngine()
        overdraft  = OverdraftEngine(self.params, self.ledger)
        exit_year  = self.params.exit_params.exit_year
        exit_eng   = None  # Exit年になるまで None のまま

        # ==================================================
        # 年次ループ（sim_year: 1 始まり）
        # ==================================================
        for sim_year in range(1, self.params.holding_years + 1):

            # ★ カレンダー年を計算する（ledger.year列と必ず一致させること）
            # sim_year=1 → start_date.year（例：2025）
            # sim_year=2 → start_date.year + 1（例：2026）
            calendar_year = self.start_date.year + sim_year - 1

            # ----------------------------------------------
            # Phase 2: 月次フェーズ（1月〜12月）
            #   各月の家賃収入・費用・減価償却・借入返済を仕訳生成する。
            #   追加設備はinv.yearとsim_yearが一致する月（1月）に取得処理。
            # ----------------------------------------------
            for month in range(1, 13):
                sim_month_index = (sim_year - 1) * 12 + month
                self.state.current_month = sim_month_index
                d0 = self.map_sim_to_calendar(sim_month_index)
                monthly.generate(sim_month_index)

                # 前年の税金を2月に預金から払う（Excel 版 765・968 行）
                if month == 2 and sim_year >= 2:
                    tax_engine.settle_tax_balances(self.ledger, d0)

                # 当座借越：前月末残高に対する利息を払い（Excel 版 923 行）、
                # 月末に借りるか返す（952・953 行）。
                # 売却月（売却年の12月）は売却・納税のあとで一括返済する。
                overdraft.accrue_interest(d0)
                if not (sim_year == exit_year and month == 12):
                    overdraft.settle_month_end(d0)

            # ----------------------------------------------
            # Phase 3: Exit フェーズ（Exit年のみ）
            #   月次12月完了後・消費税精算前に実行する（仕様書9章）。
            #   固定資産売却仮勘定方式で売却益（損）を確定させる。
            # ----------------------------------------------
            if sim_year == exit_year:
                exit_eng = ExitEngine()
                exit_eng.execute_exit(self.params, self.state, self.ledger)

            # ----------------------------------------------
            # Phase 4: 消費税精算
            #   仮払消費税・仮受消費税を相殺し、
            #   差額を未払消費税（納税）または未収還付消費税（還付）へ振替。
            #   ★ calendar_year を渡す（ledger.year列と一致させるため）
            # ----------------------------------------------
            year_end.generate_year_end(calendar_year)

            # ----------------------------------------------
            # Phase 5: 税計算
            #   税引前利益を計算し、欠損金繰越控除を適用後、
            #   所得税（法人税）と未払所得税（法人税）を計上する。
            #   ★ calendar_year を渡す（ledger.year列と一致させるため）
            # ----------------------------------------------
            tax_engine.calculate_tax(
                params=self.params,
                state_manager=self.state,
                ledger=self.ledger,
                current_year=calendar_year,
            )

            # ----------------------------------------------
            # Phase 6: 最終精算（Exit年のみ・Tax Phase後）
            #   当座借越借入金・未払消費税・未払所得税（法人税）等を
            #   元入金へ振替し、BSを最終形（預金・元入金・繰越利益剰余金のみ）に整える。
            # ----------------------------------------------
            if sim_year == exit_year and exit_eng is not None:
                # Phase 6a: 出口の年の税金を売却月に預金から払う
                #   （Excel 版 968 行「出口月は当月納付」、765 行）
                sell_date = date(calendar_year, 12, 31)
                tax_engine.settle_tax_balances(self.ledger, sell_date, "（出口）")

                # Phase 6b: 当座借越を預金から一括返済し、不足は元入金で埋める
                #   （Excel 版 863・952 行）
                overdraft.settle_at_exit(sell_date)

                # Phase 6c: 残高を元入金へ振り替える安全策。
                #   6a・6b のあとは通常すべて 0 で、仕訳は作られない。
                exit_eng.post_final_settlement_entries(self.state, self.ledger)

            # 売却の年で終わる（Excel 版：出口月以降はゼロ）
            if sim_year >= exit_year:
                break

# ===============================
# core/simulation/simulation.py end
# ===============================