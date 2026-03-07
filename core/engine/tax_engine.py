# =======================================
# core/engine/tax_engine.py
# 仕様書 第10章 TaxEngine 準拠版
# =======================================
#
# 【責務】
#   年次の所得税（法人税）計算と仕訳計上、および欠損金繰越控除を担当する。
#
# 【処理順序（仕様書10.2節 絶対厳守）】
#   1. extract_pre_tax_income   : ledgerから当期税引前利益を抽出
#   2. apply_loss_carryforward  : 欠損金繰越控除を適用し課税所得を確定
#   3. compute_tax_amount       : 税額計算
#   4. post_tax_journal_entries : 仕訳計上（所得税（法人税）／未払所得税（法人税））
#
# 【重要：calendar_year について】
#   ledger.get_df() の year 列はカレンダー年（例：2025）。
#   simulation.py から calendar_year を受け取り、ledger.year と直接突き合わせる。
#   sim_year（1, 2, 3...）を受け取ってはいけない。
#
# 【欠損金繰越期間（システム固定値・仕様書10.3節）】
#   法人（corporate）  : 10年
#   個人（individual） :  3年
#
# =======================================

import datetime
from core.ledger.journal_entry import JournalEntry


# 欠損金繰越上限年数（仕様書10.3節）
_LOSS_CARRYFORWARD_YEARS = {
    "corporate":  10,
    "individual":  3,
}

# -----------------------------------------------------------------------
# BS科目セット
# extract_pre_tax_income でPL科目のみを抽出するために除外するBS科目一覧。
# BS科目は借方・貸方の残高で損益計算しない。
# -----------------------------------------------------------------------
_BS_ACCOUNTS = {
    # 流動資産
    "預金",
    "未収還付消費税",
    "仮払消費税",
    # 固定資産
    "建物",
    "建物減価償却累計額",
    "追加設備",
    "追加設備減価償却累計額",
    "土地",
    # 流動負債
    "未払消費税",
    "未払所得税（法人税）",
    # 仮勘定
    "仮受消費税",
    "固定資産売却仮勘定",
    # 固定負債
    "長期借入金",
    "追加設備投資借入金",
    "当座借越借入金",
    # 純資産
    "元入金",
    "繰越利益剰余金",
}


class TaxEngine:
    """
    仕様書 第10章 TaxEngine

    年次の所得税（法人税）を計算し、ledgerに仕訳を計上する。
    StateManager の loss_carryforward_list を更新・参照する。
    """

    # --------------------------------------------------------
    # 統合API（simulation.py が呼ぶ唯一のエントリポイント）
    # --------------------------------------------------------
    def calculate_tax(self, params, state_manager, ledger, current_year: int) -> None:
        """
        Parameters
        ----------
        params        : SimulationParams（entity_type / effective_tax_rate を参照）
        state_manager : StateManager（loss_carryforward_list を読み書き）
        ledger        : LedgerManager（仕訳抽出・計上先）
        current_year  : int  カレンダー年（例：2025, 2026）
                        simulation.py が calendar_year を渡すこと。
        """
        # Step 1: 税引前利益を抽出
        pre_tax_income = self.extract_pre_tax_income(ledger, current_year)

        # Step 2: 欠損金繰越控除を適用し課税所得を確定
        taxable_income = self.apply_loss_carryforward(
            pre_tax_income=pre_tax_income,
            state_manager=state_manager,
            entity_type=params.entity_type,
            current_year=current_year,
        )

        # Step 3: 税額計算
        tax_amount = self.compute_tax_amount(taxable_income, params.effective_tax_rate)

        # Step 4: 税額がある場合のみ仕訳計上
        if tax_amount > 0:
            self.post_tax_journal_entries(tax_amount, ledger, current_year)

    # --------------------------------------------------------
    # Step 1: 税引前利益の抽出
    # --------------------------------------------------------
    def extract_pre_tax_income(self, ledger, current_year: int) -> float:
        """
        当期（calendar_year）の全PL仕訳から税引前利益を算出する。

        計算式：
            税引前利益 = 貸方合計（収益）- 借方合計（費用）
                         ※ BS科目・所得税（法人税）科目は除外

        Returns
        -------
        float : 税引前利益（負の場合は当期純損失）
        """
        df = ledger.get_df()
        if df is None or df.empty:
            return 0.0

        # ★ calendar_year で当期仕訳を絞り込む
        df = df[df["year"] == current_year]

        # BS科目と税関連科目を除外してPL科目のみにする
        # 所得税（法人税）は税引前利益の計算に含めない
        EXCLUDE = _BS_ACCOUNTS | {"所得税（法人税）"}
        df = df[~df["account"].isin(EXCLUDE)]

        credit_total = float(df[df["dr_cr"] == "credit"]["amount"].sum())
        debit_total  = float(df[df["dr_cr"] == "debit" ]["amount"].sum())

        return credit_total - debit_total

    # --------------------------------------------------------
    # Step 2: 欠損金繰越控除の適用（仕様書10.3節）
    # --------------------------------------------------------
    def apply_loss_carryforward(
        self, pre_tax_income: float, state_manager, entity_type: str, current_year: int
    ) -> float:
        """
        欠損金繰越リスト（state_manager.loss_carryforward_list）を操作し、
        課税所得を返す。

        処理手順：
            1. 期限切れ欠損金を除去（発生年から max_years 経過したもの）
            2. 古い順に欠損金を充当し、課税所得を確定
            3. 当期が欠損（pre_tax_income < 0）なら新規欠損金として登録

        Parameters
        ----------
        entity_type : "corporate" or "individual"
        current_year : カレンダー年

        Returns
        -------
        float : 課税所得（0以上）
        """
        max_years = _LOSS_CARRYFORWARD_YEARS.get(entity_type, 3)

        # --- 期限切れ除去 ---
        state_manager.loss_carryforward_list = [
            (yr, amt)
            for yr, amt in state_manager.loss_carryforward_list
            if (current_year - yr) < max_years
        ]

        # --- 古い順に充当 ---
        remaining = pre_tax_income
        new_list  = []
        for yr, loss_amt in state_manager.loss_carryforward_list:
            if remaining <= 0:
                # 既に課税所得がゼロ以下 → 残りの欠損金は繰り越す
                new_list.append((yr, loss_amt))
            elif loss_amt <= remaining:
                # 欠損金全額を充当できる
                remaining -= loss_amt
                # この欠損金は使い切ったのでnew_listに追加しない
            else:
                # 欠損金の一部だけ充当し、残りを繰り越す
                new_list.append((yr, loss_amt - remaining))
                remaining = 0.0

        state_manager.loss_carryforward_list = new_list

        # --- 当期欠損金の新規登録 ---
        if pre_tax_income < 0:
            state_manager.loss_carryforward_list.append(
                (current_year, abs(pre_tax_income))
            )

        # 課税所得は0以上
        return max(0.0, remaining)

    # --------------------------------------------------------
    # Step 3: 税額計算
    # --------------------------------------------------------
    def compute_tax_amount(self, taxable_income: float, tax_rate: float) -> float:
        """
        課税所得 × 実効税率 = 税額

        課税所得がゼロ以下の場合は 0 を返す。
        """
        if taxable_income <= 0:
            return 0.0
        return taxable_income * tax_rate

    # --------------------------------------------------------
    # Step 4: 税仕訳の計上
    # --------------------------------------------------------
    def post_tax_journal_entries(self, tax_amount: float, ledger, current_year: int) -> None:
        """
        所得税（法人税）を費用計上し、未払所得税（法人税）を負債計上する。

        仕訳：
            借）所得税（法人税）    tax_amount
            貸）未払所得税（法人税） tax_amount

        日付：当期12月31日（期末）
        """
        entry_date = datetime.date(current_year, 12, 31)

        entry = JournalEntry(
            date=entry_date,
            description="所得税（法人税）計上",
            dr_account="所得税（法人税）",
            dr_amount=tax_amount,
            cr_account="未払所得税（法人税）",
            cr_amount=tax_amount,
        )
        ledger.add_entry(entry)

# =======================================
# core/engine/tax_engine.py end
# =======================================