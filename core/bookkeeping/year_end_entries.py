# ===============================================
# core/bookkeeping/year_end_entries.py
# 仕様書 第8章 YearEndEntryGenerator 準拠版
# ===============================================
#
# 【責務】
#   期末の消費税精算仕訳（仮払消費税・仮受消費税の相殺）を担当する。
#   損益振替は行わない（PLとBSはledger集計から直接生成する設計）。
#
# 【処理内容（仕様書8.2節）】
#   1. 当期の仮払消費税残高（借方残）と仮受消費税残高（貸方残）を取得
#   2. 仮受 > 仮払 → 差額を未払消費税へ（納税ケース）
#   3. 仮払 > 仮受 → 差額を未収還付消費税へ（還付ケース）
#   4. 差額ゼロ   → 仕訳なし
#
# 【重要：calendar_year について】
#   ledger.get_df() の year 列はカレンダー年（例：2025）。
#   simulation.py から calendar_year（例：2025, 2026...）を受け取り、
#   ledger の year 列と直接突き合わせてフィルタする。
#   sim_year（1, 2, 3...）を受け取ってはいけない。
#
# ===============================================

from datetime import date
from core.ledger.journal_entry import make_entry_pair


class YearEndEntryGenerator:
    """
    仕様書 第8章 YearEndEntryGenerator

    消費税精算仕訳を生成する。
    """

    def __init__(self, params, ledger, start_year: int):
        self.p          = params
        self.ledger     = ledger
        self.start_year = start_year  # 取得年（参照用・現状未使用だが拡張に備えて保持）

    # --------------------------------------------------------
    # 消費税精算メイン（仕様書8.3節 generate_year_end(calendar_year)）
    # --------------------------------------------------------
    def generate_year_end(self, calendar_year: int) -> None:
        """
        Parameters
        ----------
        calendar_year : int
            実カレンダー年（例：2025, 2026, 2027）。
            simulation.py が calendar_year を渡す。
            ledger.get_df() の year 列と必ず一致していること。
        """
        # 期末日を仕訳日付として使用
        close_date = date(calendar_year, 12, 31)

        # 当期の仮払消費税残高（借方残 = 資産科目）
        vat_paid = self._balance("仮払消費税", calendar_year, asset=True)

        # 当期の仮受消費税残高（貸方残 = 負債科目）
        vat_received = self._balance("仮受消費税", calendar_year, asset=False)

        diff = vat_received - vat_paid

        if diff > 0:
            # ============================================================
            # 納税ケース：仮受 > 仮払
            #   仮払消費税・仮受消費税を全額相殺し、差額を未払消費税へ
            #   借）仮受消費税 vat_paid  ／ 貸）仮払消費税 vat_paid
            #   借）仮受消費税 diff      ／ 貸）未払消費税  diff
            # ============================================================
            self.ledger.add_entries(make_entry_pair(
                close_date, "仮受消費税", "仮払消費税", vat_paid
            ))
            self.ledger.add_entries(make_entry_pair(
                close_date, "仮受消費税", "未払消費税", diff
            ))

        elif diff < 0:
            # ============================================================
            # 還付ケース：仮払 > 仮受
            #   仮払・仮受を全額相殺し、差額を未収還付消費税（資産）へ
            #   借）仮受消費税       vat_received ／ 貸）仮払消費税     vat_received
            #   借）未収還付消費税   abs(diff)    ／ 貸）仮払消費税     abs(diff)
            # ============================================================
            self.ledger.add_entries(make_entry_pair(
                close_date, "仮受消費税", "仮払消費税", vat_received
            ))
            self.ledger.add_entries(make_entry_pair(
                close_date, "未収還付消費税", "仮払消費税", abs(diff)
            ))

        # diff == 0 → 仕訳なし（完全相殺のため処理不要）

    # --------------------------------------------------------
    # 勘定科目残高取得ヘルパー
    # --------------------------------------------------------
    def _balance(self, account: str, calendar_year: int, asset: bool) -> float:
        """
        指定した勘定科目の当期残高を返す。

        Parameters
        ----------
        account       : 勘定科目名
        calendar_year : カレンダー年（ledger.year列と一致）
        asset         : True  → 資産科目（借方残 = dr - cr を返す）
                        False → 負債科目（貸方残 = cr - dr を返す）
        """
        df = self.ledger.get_df()
        if df is None or df.empty:
            return 0.0

        # ★ year列はカレンダー年で直接フィルタ
        df = df[(df["year"] == calendar_year) & (df["account"] == account)]
        if df.empty:
            return 0.0

        dr = float(df[df["dr_cr"] == "debit" ]["amount"].sum())
        cr = float(df[df["dr_cr"] == "credit"]["amount"].sum())

        # 資産科目（仮払消費税）→ 借方残
        # 負債科目（仮受消費税）→ 貸方残
        return (dr - cr) if asset else (cr - dr)

# ===============================================
# core/bookkeeping/year_end_entries.py end
# ===============================================