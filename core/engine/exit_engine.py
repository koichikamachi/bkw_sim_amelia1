# =======================================
# core/engine/exit_engine.py
# 仕様書 第9章 Exit Engine 準拠版
# =======================================
#
# 【配置】 core/engine/exit_engine.py
#
# 【外部から呼ぶメソッド（simulation.pyが呼ぶ）】
#   1. execute_exit(params, state_manager, ledger)
#        Exit年の12月月次完了後・消費税精算前に呼ぶ
#        → 売却代金受取・簿価消去・売却費用・借入金完済
#
#   2. post_final_settlement_entries(state_manager, ledger)
#        Tax Phase完了後に呼ぶ（仕様書9.2節ステップ8）
#        → 当座借越借入金・未払消費税・未収還付消費税・未払所得税を元入金へ精算
#
# 【責務外（委譲済み）】
#   - 消費税精算仕訳 → YearEndEntryGenerator
#   - 税額計算・税仕訳 → TaxEngine
# =======================================

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.params import SimulationParams
    from core.simulation.state_manager import StateManager
    from core.ledger.ledger import LedgerManager


class ExitEngine:
    """
    仕様書 第9章 Exit Engine

    固定資産売却仮勘定方式（仕様書9.4節）で売却仕訳を生成する。
    消費税精算・税計算は本クラスの責務外。
    """

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------
    @staticmethod
    def _split_incl_tax(amount_incl: float, tax_rate: float):
        """税込金額を（税抜, 消費税）に分割。円未満切捨て。"""
        excl = int(amount_incl / (1 + tax_rate))
        vat  = amount_incl - excl
        return float(excl), float(vat)

    @staticmethod
    def _get_account_balance(ledger, account: str) -> float:
        """
        指定勘定の正残高を返す。
        資産・費用（借方残高）: debit - credit
        負債・収益（貸方残高）: credit - debit
        ※ 本メソッドは「借方残高」として返す（呼び出し側で解釈する）
        """
        df = ledger.get_df()
        if df is None or df.empty:
            return 0.0
        sub = df[df["account"] == account]
        debit  = sub[sub["dr_cr"] == "debit" ]["amount"].sum()
        credit = sub[sub["dr_cr"] == "credit"]["amount"].sum()
        return float(debit - credit)

    # ------------------------------------------------------------------
    # 1. 外部API: execute_exit
    # ------------------------------------------------------------------
    def execute_exit(
        self,
        params: "SimulationParams",
        state_manager: "StateManager",
        ledger: "LedgerManager",
    ) -> None:
        """
        仕様書9.3節 Exit Engine 実行順序：
            1. 売却代金の受取（建物：税抜＋仮受消費税、土地：非課税）
            2. 固定資産の簿価消去
            3. 売却費用の計上
            4. 固定資産売却仮勘定の残高を損益へ振替
            5. 借入金の完済
        """
        ep        = params.exit_params
        exit_year = ep.exit_year
        sell_date = date(params.start_date.year + exit_year - 1, 12, 31)

        from core.ledger.journal_entry import make_entry_pair

        # ---- 内部ヘルパー ----
        def add(dr, cr, amt):
            if amt > 0:
                for e in make_entry_pair(sell_date, dr, cr, amt):
                    ledger.add_entry(e)

        # ==================================================
        # Step 1: 売却代金の受取
        # ==================================================
        # 建物（税込 → 税抜 + 仮受消費税）
        bld_excl, bld_vat = self._split_incl_tax(
            ep.building_exit_price, params.consumption_tax_rate
        )
        add("預金", "固定資産売却仮勘定", bld_excl)
        add("預金", "仮受消費税",         bld_vat)

        # 土地（非課税・消費税なし）
        add("預金", "固定資産売却仮勘定", ep.land_exit_price)

        # ==================================================
        # Step 2: 固定資産の簿価消去
        # ==================================================
        # ---- 建物 ----
        bld_cost  = self._get_account_balance(ledger, "建物")
        # 建物減価償却累計額（BS科目）の貸方残高 = 累計償却額
        bld_dep_total = abs(
            ledger.get_df()[
                (ledger.get_df()["account"] == "建物減価償却累計額") &
                (ledger.get_df()["dr_cr"]   == "credit")
            ]["amount"].sum()
            -
            ledger.get_df()[
                (ledger.get_df()["account"] == "建物減価償却累計額") &
                (ledger.get_df()["dr_cr"]   == "debit")
            ]["amount"].sum()
        )
        bld_book = max(0.0, bld_cost - bld_dep_total)

        if bld_dep_total > 0:
            add("建物減価償却累計額", "建物", bld_dep_total)
        if bld_book > 0:
            add("固定資産売却仮勘定", "建物", bld_book)

        # ---- 追加設備 ----
        add_cost = self._get_account_balance(ledger, "追加設備")
        # 追加設備減価償却累計額（BS科目）の貸方残高
        add_dep_total = abs(
            ledger.get_df()[
                (ledger.get_df()["account"] == "追加設備減価償却累計額") &
                (ledger.get_df()["dr_cr"]   == "credit")
            ]["amount"].sum()
            -
            ledger.get_df()[
                (ledger.get_df()["account"] == "追加設備減価償却累計額") &
                (ledger.get_df()["dr_cr"]   == "debit")
            ]["amount"].sum()
        )
        add_book = max(0.0, add_cost - add_dep_total)

        if add_dep_total > 0:
            add("追加設備減価償却累計額", "追加設備", add_dep_total)
        if add_book > 0:
            add("固定資産売却仮勘定", "追加設備", add_book)

        # ---- 土地 ----
        land_cost = self._get_account_balance(ledger, "土地")
        if land_cost > 0:
            add("固定資産売却仮勘定", "土地", land_cost)

        # ==================================================
        # Step 3: 売却費用の計上
        # ==================================================
        if ep.exit_cost > 0:
            cost_excl, cost_vat = self._split_incl_tax(
                ep.exit_cost, params.consumption_tax_rate
            )
            taxable_ratio   = 1.0 - params.non_taxable_proportion
            deductible_vat  = cost_vat * taxable_ratio
            nondeductible_vat = cost_vat * params.non_taxable_proportion

            add("固定資産売却仮勘定", "預金", cost_excl)
            if nondeductible_vat > 0:
                add("固定資産売却仮勘定", "預金", nondeductible_vat)
            if deductible_vat > 0:
                add("仮払消費税", "預金", deductible_vat)

        # ==================================================
        # Step 4: 固定資産売却仮勘定の残高を損益へ振替
        # ==================================================
        # 残高 = 貸方合計 - 借方合計（貸方残がプラス = 売却益）
        df = ledger.get_df()
        kari = df[df["account"] == "固定資産売却仮勘定"]
        kari_cr = kari[kari["dr_cr"] == "credit"]["amount"].sum()
        kari_dr = kari[kari["dr_cr"] == "debit" ]["amount"].sum()
        net = kari_cr - kari_dr

        if net > 0:
            # 売却益
            add("固定資産売却仮勘定", "固定資産売却益（損）", net)
        elif net < 0:
            # 売却損
            add("固定資産売却益（損）", "固定資産売却仮勘定", abs(net))

        # ==================================================
        # Step 5: 借入金の完済（残高を全額返済）
        # ==================================================
        # 長期借入金（初期）
        loan_balance = self._get_loan_balance(ledger, "長期借入金")
        if loan_balance > 0:
            add("長期借入金", "預金", loan_balance)

        # 追加設備投資借入金
        add_loan_balance = self._get_loan_balance(ledger, "追加設備投資借入金")
        if add_loan_balance > 0:
            add("追加設備投資借入金", "預金", add_loan_balance)

    # ------------------------------------------------------------------
    # 2. 外部API: post_final_settlement_entries
    # ------------------------------------------------------------------
    def post_final_settlement_entries(
        self,
        state_manager: "StateManager",
        ledger: "LedgerManager",
    ) -> None:
        """
        仕様書9.2節ステップ8・0.7節「Exit年の最終精算」

        Tax Phase完了後に実行する。
        以下の残高勘定を元入金へ精算する（相手勘定はすべて元入金）：
            ① 当座借越借入金
            ② 未払消費税（通常は納税で消える）
            ③ 未収還付消費税（還付ケース）
            ④ 未払所得税（法人税）

        精算後の最終BSに残るのは：
            預金・元入金・繰越利益剰余金 のみ

        返り値：なし（ledgerを直接更新）
        """
        from core.ledger.journal_entry import make_entry_pair

        # 売却日（最終精算は年末）
        df = ledger.get_df()
        if df is not None and not df.empty:
            settlement_date = df["date"].max()
        else:
            return

        def add(dr, cr, amt):
            if amt > 0:
                for e in make_entry_pair(settlement_date, dr, cr, amt):
                    ledger.add_entry(e)

        # ① 当座借越借入金 → 元入金
        od_balance = self._get_loan_balance(ledger, "当座借越借入金")
        if od_balance > 0:
            add("当座借越借入金", "元入金", od_balance)

        # ② 未払消費税 → 元入金
        vat_payable = self._get_liability_balance(ledger, "未払消費税")
        if vat_payable > 0:
            add("未払消費税", "元入金", vat_payable)

        # ③ 未収還付消費税 → 元入金（資産なので逆仕訳）
        vat_refund = self._get_asset_balance(ledger, "未収還付消費税")
        if vat_refund > 0:
            add("元入金", "未収還付消費税", vat_refund)

        # ④ 未払所得税（法人税）→ 元入金
        tax_payable = self._get_liability_balance(ledger, "未払所得税（法人税）")
        if tax_payable > 0:
            add("未払所得税（法人税）", "元入金", tax_payable)

    # ------------------------------------------------------------------
    # 内部ヘルパー：各種残高取得
    # ------------------------------------------------------------------
    def _get_loan_balance(self, ledger, account: str) -> float:
        """負債（借入金）の残高：貸方合計 - 借方合計"""
        df = ledger.get_df()
        if df is None or df.empty:
            return 0.0
        sub = df[df["account"] == account]
        credit = sub[sub["dr_cr"] == "credit"]["amount"].sum()
        debit  = sub[sub["dr_cr"] == "debit" ]["amount"].sum()
        return float(max(0.0, credit - debit))

    def _get_liability_balance(self, ledger, account: str) -> float:
        """負債科目の残高：貸方 - 借方"""
        return self._get_loan_balance(ledger, account)

    def _get_asset_balance(self, ledger, account: str) -> float:
        """資産科目の残高：借方 - 貸方"""
        df = ledger.get_df()
        if df is None or df.empty:
            return 0.0
        sub = df[df["account"] == account]
        debit  = sub[sub["dr_cr"] == "debit" ]["amount"].sum()
        credit = sub[sub["dr_cr"] == "credit"]["amount"].sum()
        return float(max(0.0, debit - credit))

# =======================================
# core/engine/exit_engine.py end
# =======================================