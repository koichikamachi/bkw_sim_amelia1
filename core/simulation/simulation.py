# ===============================
# core/simulation/simulation.py
# ===============================

from datetime import date
from config.params import SimulationParams
from core.ledger.ledger import LedgerManager
from core.bookkeeping.initial_entries import InitialEntryGenerator
from core.bookkeeping.monthly_entries import MonthlyEntryGenerator
from core.bookkeeping.year_end_entries import YearEndEntryGenerator
from core.ledger.journal_entry import make_entry_pair


class Simulation:
    def __init__(self, params: SimulationParams, start_date: date):
        self.params = params
        self.start_date = start_date
        self.ledger = LedgerManager()
        

    # ------------------------------------------------------------
    # ★★ 月インデックス → 実カレンダー日付 の最新方式（完全版）★★
    # ------------------------------------------------------------
    def map_sim_to_calendar(self, sim_month_index: int):
        """
        sim_month_index = 1,2,3,... の通算月 → date(Y, M, 1)
        """
        idx = sim_month_index - 1

        year = self.start_date.year + (idx // 12)
        month = ((self.start_date.month - 1) + (idx % 12)) % 12 + 1

        return date(year, month, 1)

    # ------------------------------------------------------------
    # シミュレーション run()
    # ------------------------------------------------------------
    def run(self):
        import streamlit as st
    
        st.write("🔵 <b>ENTERED Simulation.run()</b>", unsafe_allow_html=True)
        st.write("📦 <b>Current Depreciation Units:</b>", unsafe_allow_html=True)
        st.write(self.ledger.depreciation_units)

        init = InitialEntryGenerator(self.params, self.ledger)
        init.generate(self.start_date)
        st.write("🧾 <b>Initial entries generated.</b>", unsafe_allow_html=True)
    
        # ★ 新方式：calendar_mapper を渡す
        monthly = MonthlyEntryGenerator(
            params=self.params,
            ledger=self.ledger,
            calendar_mapper=self.map_sim_to_calendar
        )
        monthly.simulation = self

        year_end = YearEndEntryGenerator(
            self.params,
            self.ledger,
            self.start_date.year
        )

        # ----------------- 月次ループ -----------------
        for year in range(1, self.params.holding_years + 1):
            for month in range(1, 13):

                try:
                    sim_month_index = (year - 1) * 12 + month
                    monthly.generate(sim_month_index)

                except Exception as e:
                    st.error(f"ERROR in monthly.generate(sim_month_index={sim_month_index}): {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    raise

        # ----------------- EXIT 処理 -----------------
        self._generate_exit_entries()

        return self.ledger.get_df()


    # ------------------------------------------------------------
    # EXIT（売却・除却の総合処理）
    # ------------------------------------------------------------
    def _generate_exit_entries(self):

        ep = self.params.exit_params
        exit_year = ep.exit_year
        land_exit = ep.land_exit_price
        bld_exit = ep.building_exit_price
        exit_cost = ep.exit_cost

        sell_date = date(self.start_date.year + exit_year - 1, 12, 31)

        df = self.ledger.get_df()

        # ===========================
        # 1. 帳簿価額の抽出
        # ===========================
        land_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "土地")]["amount"].sum()
        land_book = land_acq

        bld_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "建物")]["amount"].sum()
        bld_dep = df[(df["dr_cr"] == "debit") & (df["account"] == "建物減価償却費")]["amount"].sum()
        bld_book = bld_acq - bld_dep

        add_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "追加設備")]["amount"].sum()
        add_dep = df[(df["dr_cr"] == "debit") & (df["account"] == "追加設備減価償却費")]["amount"].sum()
        add_book = add_acq - add_dep

        # ===========================================================
        # ★★ 2. 修正：売却代金は「特別利益」（建物・土地別）★★
        # ===========================================================
        if land_exit > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "預金", "特別利益", land_exit
            ))

        if bld_exit > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "預金", "特別利益", bld_exit
            ))

        # ===========================================================
        # ★★ 3. 資産除却の正しい仕訳（簿価＝特別損失）★★
        # ===========================================================

        # ---- 土地 ----
        if land_book > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "特別損失", "土地", land_book
            ))

        # ---- 建物（減価償却累計 → 建物減額 → 残簿価損失）----
        if bld_acq > 0:

            if bld_dep > 0:
                self.ledger.add_entries(make_entry_pair(
                    sell_date, "建物減価償却累計額", "建物", bld_dep
                ))

            if bld_book > 0:
                self.ledger.add_entries(make_entry_pair(
                    sell_date, "特別損失", "建物", bld_book
                ))

        # ---- 追加設備 ----
        if add_acq > 0:

            if add_dep > 0:
                self.ledger.add_entries(make_entry_pair(
                    sell_date, "追加設備減価償却累計額", "追加設備", add_dep
                ))

            if add_book > 0:
                self.ledger.add_entries(make_entry_pair(
                    sell_date, "特別損失", "追加設備", add_book
                ))

        # ===========================================================
        # ★★ 4. 売却費用も特別損失★★
        # ===========================================================
        if exit_cost > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "特別損失", "預金", exit_cost
            ))

        # ===========================================================
        # ★★ 5. 期末に特別利益と特別損失を相殺する★★
        # ===========================================================
        df2 = self.ledger.get_df()

        total_gain = df2[(df2["dr_cr"] == "credit") & 
                         (df2["account"] == "特別利益")]["amount"].sum()

        total_loss = df2[(df2["dr_cr"] == "debit") & 
                         (df2["account"] == "特別損失")]["amount"].sum()

        net = total_gain - total_loss

        # ---- 利益が勝つ → 損失を取り消す仕訳 ----
        if net > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "特別損失", "特別利益", total_loss
            ))

        # ---- 損失が勝つ → 利益を取り消す仕訳 ----
        elif net < 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "特別利益", "特別損失", total_gain
            ))

# ===============================
# END OF FILE
# ===============================
