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
    # ★ シミュレーション year → 実カレンダー年への変換
    # ------------------------------------------------------------
    def map_sim_to_calendar(self, sim_year: int, month: int):
        cal_year = self.start_date.year + (sim_year - 1)
        cal_month = month
        return cal_year, cal_month

    # ============================================================
    # シミュレーション run()
    # ============================================================

    def run(self):
        # raise Exception("RUN ENTERED TEST")
        import streamlit as st
    
        # ---- UI に確実に出るログ（最重要）----
        st.write("🔵 <b>ENTERED Simulation.run()</b>", unsafe_allow_html=True)
    
        # ---- 減価償却ユニットの中身を UI に表示 ----
        st.write("📦 <b>Current Depreciation Units:</b>", unsafe_allow_html=True)
        st.write(self.ledger.depreciation_units)
    
        # ---- ターミナル側にもログ（任意）----
        print("### ENTERED Simulation.run() ###")
        print("DEPRECIATION UNITS:", self.ledger.depreciation_units)
    
        # ---------------------- 初期投資仕訳 ----------------------
        from core.bookkeeping.initial_entries import InitialEntryGenerator
        init = InitialEntryGenerator(self.params, self.ledger)
        init.generate(self.start_date)
        st.write("🧾 <b>Initial entries generated.</b>", unsafe_allow_html=True)
    
        # ---------------------- 建物の償却ユニット登録（追加） ----------------------
        from core.depreciation.unit import DepreciationUnit
        bld_unit = DepreciationUnit(
            acquisition_cost=self.params.property_price_building,
            useful_life_years=self.params.building_useful_life,
            start_year=self.start_date.year,
            start_month=self.start_date.month,
            asset_type="building"
        )
        self.ledger.register_depreciation_unit(bld_unit)
    
        st.write("🏢 <b>Building depreciation unit registered.</b>", unsafe_allow_html=True)
        st.write(bld_unit)
    
        # ---- ターミナルにも（任意）----
        print("REGISTERED BUILDING UNIT:", bld_unit)
        print("DEPR UNITS:", self.ledger.depreciation_units)
    
    
        # ---------------------- ここから元の run の実処理 ----------------------
        # （月次処理などが続く）
    
        
        

        # ---------------------- 初期投資仕訳 ----------------------
        InitialEntryGenerator(
            self.params,
            self.ledger
        ).generate(self.start_date)

        # 【追加：ここを足して！】建物の償却ユニットを登録
        from core.depreciation.unit import DepreciationUnit
        bld_unit = DepreciationUnit(
            acquisition_cost=self.params.property_price_building,
            useful_life_years=self.params.building_useful_life,
            start_year=self.start_date.year,
            start_month=self.start_date.month,
            asset_type="building"
        )
        self.ledger.register_depreciation_unit(bld_unit)

        # ---------------------- 月次／年次生成器 -------------------
        monthly = MonthlyEntryGenerator(
            params=self.params,
            ledger=self.ledger,
            start_date=self.start_date
        )
        # ★ ここが今回の本丸（暦変換ブリッジの注入）
        monthly.simulation = self
        year_end = YearEndEntryGenerator(
            self.params,
            self.ledger,
            self.start_date.year
        )

        # ============================================================
        # メインループ
        # ============================================================
        for year in range(1, self.params.holding_years + 1):

            # --- 月次 ---
            for month in range(1, 13):
                monthly.generate_month(year, month)

            # --- 年次 ---
            year_end.generate_year_end(
                year,
                monthly.vat_received,
                monthly.vat_paid,
                monthly.monthly_profit_total
            )

            # reset
            monthly.vat_received = 0.0
            monthly.vat_paid = 0.0
            monthly.monthly_profit_total = 0.0

        # ============================================================
        # EXIT（売却）仕訳生成
        # ============================================================
        self._generate_exit_entries()

        # 完了：Ledger 全体
        return self.ledger.get_df()

    # ------------------------------------------------------------
    # EXIT（売却仕訳）
    # ------------------------------------------------------------
    def _generate_exit_entries(self):

        ep = self.params.exit_params
        exit_year = ep.exit_year
        land_exit = ep.land_exit_price
        bld_exit = ep.building_exit_price
        exit_cost = ep.exit_cost

        sell_date = date(self.start_date.year + exit_year - 1, 12, 31)

        df = self.ledger.get_df()

        # -----------------------------
        # 帳簿価額の抽出
        # -----------------------------
        # 建物原価
        bld_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "建物")]["amount"].sum()

        # ★ 累計減価償却額の計算（建物減価償却費の合計）
        bld_dep = df[(df["dr_cr"] == "debit") & (df["account"] == "建物減価償却費")]["amount"].sum()

        # ★ 帳簿価額（建物簿価）
        bld_book = bld_acq - bld_dep

        # 追加設備
        add_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "追加設備")]["amount"].sum()
        add_dep = df[(df["dr_cr"] == "debit") & (df["account"] == "追加設備減価償却費")]["amount"].sum()
        add_book = add_acq - add_dep

        # 土地（減価償却なし）
        land_acq = df[(df["dr_cr"] == "debit") & (df["account"] == "土地")]["amount"].sum()
        land_book = land_acq

        # -----------------------------
        # 売却額 & 帳簿価額
        # -----------------------------
        total_sale = land_exit + bld_exit
        total_book = land_book + bld_book + add_book

        gain = total_sale - total_book - exit_cost

        # ============================================================
        # A) 土地売却
        # ============================================================
        if land_exit > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "預金", "土地", land_exit
            ))

        # ============================================================
        # B) 建物売却（取得価額ベース）
        # ============================================================
        if bld_exit > 0:
            # ★ 建物売却
            self.ledger.add_entries(make_entry_pair(
                sell_date, "預金", "建物", bld_exit
            ))
        # ============================================================
        # C) 追加設備売却
        # ============================================================
        if add_acq > 0:
            # 売却額は 0 → 追加設備売却額は UI が設定するならパラメータ化可
            pass

        # ============================================================
        # D) 累計減価償却の除却
        # ============================================================
        if bld_dep > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "建物減価償却累計額", "建物", bld_dep
            ))

        if add_dep > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "追加設備減価償却累計額", "追加設備", add_dep
            ))

        # ============================================================
        # E) 売却費用
        # ============================================================
        if exit_cost > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "売却費用", "預金", exit_cost
            ))

        # ============================================================
        # F) 売却益（特別利益）／売却損（特別損失）
        # ============================================================
        if gain > 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "その他", "特別利益", gain
            ))
        elif gain < 0:
            self.ledger.add_entries(make_entry_pair(
                sell_date, "特別損失", "その他", -gain
            ))


# ============= end simulation.py