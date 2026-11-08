# =======================================
# core/engine/overdraft_engine.py
# 仕様書 第14章 当座借越エンジン ／ 原型 Excel 版 FST-R b03.7
# 「演算シート」当座借越借入・当座借越返済（短期借入金モジュール）準拠
# =======================================
#
# 【Excel 版の決まり（900〜958 行・863 行）】
#   B ＝ 当月の預金の前残 ＋ 当月の入金 − 当月の出金（利息の支払いを含む）
#   ・B がマイナス → −B を借りる        （預金／当座借越借入金）
#   ・B がプラスで借越残高がある → min(B, 残高) を返す（当座借越借入金／預金）
#   ・利息 ＝ 前月末の借越残高 × 年利 ÷ 12（円で四捨五入）を当月に預金から払う
#   ・売却月は新たに借りず、借越を全額返す。預金が足りない分は元入金で埋める
#
# 【Python 版で足したもの（Excel 版にはない）】
#   ・上限（overdraft_limit）：超えたら ValueError。None なら上限なし
#   ・切替（overdraft_enabled）：False なら何もしない
#
# 【呼び出し順（simulation.py）】
#   毎月：月次仕訳 → 税金の支払い（2月）→ accrue_interest → settle_month_end
#   売却年の12月：settle_month_end は呼ばず、売却・税計算・納税のあと settle_at_exit
# =======================================

import math

from core.ledger.journal_entry import make_entry_pair

OD_ACCOUNT = "当座借越借入金"
OD_INTEREST = "当座借越利息"
DEPOSIT = "預金"
CAPITAL = "元入金"


def round_half_up(x: float) -> float:
    """Excel の ROUND(x, 0) と同じ四捨五入（0.5 は 0 から遠い側へ）"""
    if x >= 0:
        return float(math.floor(x + 0.5))
    return -float(math.floor(-x + 0.5))


class OverdraftEngine:

    def __init__(self, params, ledger):
        self.ledger = ledger
        self.rate = float(params.overdraft_interest_rate)
        self.enabled = bool(getattr(params, "overdraft_enabled", True))
        limit = getattr(params, "overdraft_limit", None)
        self.limit = None if limit is None else float(limit)

        # 入力の検証（仕様書 14-7）
        if self.rate < 0:
            raise ValueError(f"当座借越利率が負の値です：{self.rate}")
        if self.limit is not None and self.limit < 0:
            raise ValueError(f"当座借越の上限が負の値です：{self.limit}")

    # ------------------------------------------------------------
    # 残高
    # ------------------------------------------------------------
    def balance(self) -> float:
        """借越残高（貸方残、プラスで表す）"""
        return -self.ledger.get_account_balance(OD_ACCOUNT)

    def _deposit(self) -> float:
        return self.ledger.get_account_balance(DEPOSIT)

    def _add(self, d, dr, cr, amt, desc):
        if amt > 0:
            self.ledger.add_entries(make_entry_pair(d, dr, cr, amt, description=desc))

    # ------------------------------------------------------------
    # 利息（Excel 923・956 行）
    #   月の頭に呼ぶ。この時点の残高 ＝ 前月末の残高
    # ------------------------------------------------------------
    def accrue_interest(self, d) -> float:
        if not self.enabled:
            return 0.0
        interest = round_half_up(self.balance() * self.rate / 12)
        self._add(d, OD_INTEREST, DEPOSIT, interest, "当座借越利息支払")
        return interest

    # ------------------------------------------------------------
    # 月末の借入・返済（Excel 952・953 行）
    # ------------------------------------------------------------
    def settle_month_end(self, d) -> None:
        if not self.enabled:
            return
        b = self._deposit()
        prev = self.balance()

        if b < 0:
            need = -b
            if self.limit is not None and prev + need > self.limit + 0.5:
                raise ValueError(
                    f"当座借越の上限を超えました（{d:%Y-%m}）："
                    f"必要残高 {prev + need:,.0f} 円 ＞ 上限 {self.limit:,.0f} 円"
                )
            self._add(d, DEPOSIT, OD_ACCOUNT, need, "当座借越借入")
        elif b > 0 and prev > 0:
            self._add(d, OD_ACCOUNT, DEPOSIT, min(b, prev), "当座借越返済")

    # ------------------------------------------------------------
    # 売却月の一括返済（Excel 863・952 行）
    # ------------------------------------------------------------
    def settle_at_exit(self, d) -> None:
        if not self.enabled:
            return
        prev = self.balance()
        b = self._deposit()
        shortfall = prev - b          # Excel 863 行：C ＝ 借越前残 − 預金
        if shortfall > 0:
            self._add(d, DEPOSIT, CAPITAL, shortfall, "出口月の預金不足分")
        self._add(d, OD_ACCOUNT, DEPOSIT, prev, "当座借越返済（出口）")

# =======================================
# core/engine/overdraft_engine.py end
# =======================================
