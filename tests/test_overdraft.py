# ============================================================
# tests/test_overdraft.py
# 当座借越エンジン・税金の預金支払いのテスト
# 原型 Excel 版（FST-R b03.7「演算シート」900〜958 行・863 行・
# 764・765・968 行）の決まりに合わせる。
# ============================================================
#
# 【確かめること】
#   OD-01 : 月末の預金がマイナスにならない（借越が補う）
#   OD-02 : 預金が足りない月に、不足額ちょうどを借りる
#   OD-03 : 余剰の月に、min(余剰, 借越残高) を返す
#   OD-04 : 同じ月に「借りる」と「返す」が同時に起きない
#   OD-05 : 利息 = 前月末の借越残高 × 年利 ÷ 12（円で四捨五入）を当月に払う
#   OD-06 : 前年の未払消費税・未払所得税は翌年 2 月に預金から払う
#           （未収還付消費税は 2 月に受け取る）
#   OD-07 : 売却月は新たに借りず、借越を預金から全額返す。
#           足りない分は元入金で埋める（預金／元入金）
#   OD-08 : 出口の年の税金も売却月に預金から払い、元入金への振替は起きない
#   OD-09 : 毎月の借方合計 = 貸方合計
#   OD-10 : 借越の上限を超えたら ValueError
#   OD-11 : 切替を OFF にすると借越の仕訳は作られない
#   OD-12 : 利率が負なら ValueError
# ============================================================

import os
import sys
import math
import dataclasses

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.params import AdditionalInvestmentParams
from core.simulation.simulation import Simulation
from test_integration_minimal import make_minimal_params

OD = "当座借越借入金"
OD_INT = "当座借越利息"
RATE = 0.02


# ------------------------------------------------------------
# 例の組み立て
# ------------------------------------------------------------
def params_always_short(**kw):
    """家賃が少なく、最初の月から売却まで預金が足りない例（3年目に売却）。
    非課税割合 100% にして、消費税の還付で借越が返されないようにしている。"""
    p = make_minimal_params(exit_year=3, holding_years=3, annual_rent_incl=100_000,
                            non_taxable_proportion=1.0)
    return dataclasses.replace(p, overdraft_interest_rate=RATE, **kw)


def params_exit_short(**kw):
    """売却代金がほとんどなく、売却月に預金で借越を返し切れない例"""
    p = make_minimal_params(exit_year=3, holding_years=3, annual_rent_incl=100_000,
                            non_taxable_proportion=1.0,
                            land_exit_price=100_000, building_exit_price_incl=0,
                            exit_cost_incl=0)
    return dataclasses.replace(p, overdraft_interest_rate=RATE, **kw)


def params_dip_and_recover(**kw):
    """2年目1月に追加設備を自己資金で買って預金が落ち込み、その後の余剰で返す例"""
    p = make_minimal_params(exit_year=4, holding_years=4)
    inv = AdditionalInvestmentParams(
        year=2, amount=5_000_000, life=10,
        loan_amount=0, loan_years=1, loan_interest_rate=0.0,
    )
    return dataclasses.replace(
        p, overdraft_interest_rate=RATE, additional_investments=[inv], **kw
    )


def run(params):
    sim = Simulation(params, params.start_date)
    sim.run()
    return sim.ledger.get_df()


def month_keys(df):
    return sorted({(int(y), int(m)) for y, m in zip(df["year"], df["month"])})


def month_df(df, y, m):
    return df[(df["year"] == y) & (df["month"] == m)]


def upto(df, y, m):
    return df[(df["year"] < y) | ((df["year"] == y) & (df["month"] <= m))]


def dr(df, acc):
    return float(df[(df["account"] == acc) & (df["dr_cr"] == "debit")]["amount"].sum())


def cr(df, acc):
    return float(df[(df["account"] == acc) & (df["dr_cr"] == "credit")]["amount"].sum())


def od_balance(df):
    return cr(df, OD) - dr(df, OD)


def deposit(df):
    return dr(df, "預金") - cr(df, "預金")


@pytest.fixture(scope="module")
def df_short():
    return run(params_always_short())


@pytest.fixture(scope="module")
def df_dip():
    return run(params_dip_and_recover())


# ------------------------------------------------------------
# OD-01
# ------------------------------------------------------------
@pytest.mark.parametrize("name", ["df_short", "df_dip"])
def test_month_end_deposit_never_negative(name, request):
    df = request.getfixturevalue(name)
    for y, m in month_keys(df):
        bal = deposit(upto(df, y, m))
        assert bal > -1.0, f"{y}-{m:02d} 月末の預金がマイナス：{bal:,.0f}"


# ------------------------------------------------------------
# OD-02
# ------------------------------------------------------------
def test_borrow_exactly_the_shortfall(df_short):
    y, m = month_keys(df_short)[0]
    mdf = month_df(df_short, y, m)
    borrowed = cr(mdf, OD)
    assert borrowed > 0, "最初の月に借越が起きていない"
    # 借りる前の預金（B）＝ 月末の預金 − 借りた額。B のマイナス分を借りる
    b = deposit(upto(df_short, y, m)) - borrowed
    assert abs(borrowed + b) < 1.0
    assert abs(deposit(upto(df_short, y, m))) < 1.0


# ------------------------------------------------------------
# OD-03
# ------------------------------------------------------------
def test_repay_from_surplus(df_dip):
    p = params_dip_and_recover()
    exit_cal = p.start_date.year + p.exit_params.exit_year - 1
    before_exit = df_dip[df_dip["year"] < exit_cal]
    assert cr(before_exit, OD) > 0, "2年目に借越が起きていない"
    assert dr(before_exit, OD) > 0, "余剰で返していない"
    for y, m in month_keys(before_exit):
        mdf = month_df(df_dip, y, m)
        repaid = dr(mdf, OD)
        if repaid == 0:
            continue
        prev = od_balance(upto(df_dip, y, m)) + repaid - cr(mdf, OD)
        b = deposit(upto(df_dip, y, m)) + repaid
        assert abs(repaid - min(b, prev)) < 1.0, f"{y}-{m:02d} 返済額が min(B, 前残) でない"
    # 売却より前に借越はなくなっている
    assert od_balance(before_exit) < 1.0


# ------------------------------------------------------------
# OD-04
# ------------------------------------------------------------
@pytest.mark.parametrize("name", ["df_short", "df_dip"])
def test_no_borrow_and_repay_in_same_month(name, request):
    df = request.getfixturevalue(name)
    for y, m in month_keys(df):
        mdf = month_df(df, y, m)
        assert not (cr(mdf, OD) > 0 and dr(mdf, OD) > 0), f"{y}-{m:02d} 借りると返すが同時"


# ------------------------------------------------------------
# OD-05
# ------------------------------------------------------------
@pytest.mark.parametrize("name", ["df_short", "df_dip"])
def test_interest_on_previous_month_end_balance(name, request):
    df = request.getfixturevalue(name)
    keys = month_keys(df)
    for i, (y, m) in enumerate(keys):
        paid = dr(month_df(df, y, m), OD_INT)
        if i == 0:
            assert paid == 0
            continue
        py, pm = keys[i - 1]
        expected = math.floor(od_balance(upto(df, py, pm)) * RATE / 12 + 0.5)  # Excel の ROUND と同じ四捨五入
        assert abs(paid - expected) < 0.5, f"{y}-{m:02d} 利息 {paid} ≠ {expected}"
    assert dr(df, OD_INT) > 0


def test_interest_paid_from_deposit(df_short):
    sub = df_short[df_short["description"] == "当座借越利息支払"]
    assert set(sub["account"]) == {OD_INT, "預金"}


# ------------------------------------------------------------
# OD-06
# ------------------------------------------------------------
def test_prior_year_taxes_settled_in_february():
    p = dataclasses.replace(make_minimal_params(exit_year=3), overdraft_interest_rate=RATE)
    df = run(p)
    y1 = p.start_date.year
    accrued = (
        cr(df[df["year"] == y1], "未払消費税")
        + cr(df[df["year"] == y1], "未払所得税（法人税）")
        + dr(df[df["year"] == y1], "未収還付消費税")
    )
    assert accrued > 0, "1年目に未払・未収の税金が計上されていない（例の前提が崩れている）"
    # 1月末にはまだ残っている
    jan = upto(df, y1 + 1, 1)
    left_jan = (
        cr(jan, "未払消費税") - dr(jan, "未払消費税")
        + cr(jan, "未払所得税（法人税）") - dr(jan, "未払所得税（法人税）")
        + dr(jan, "未収還付消費税") - cr(jan, "未収還付消費税")
    )
    assert abs(left_jan - accrued) < 1.0
    # 2月の支払・受取は預金を通る
    feb = month_df(df, y1 + 1, 2)
    for acc in ("未払消費税", "未払所得税（法人税）", "未収還付消費税"):
        rows = feb[feb["account"] == acc]
        for desc in rows["description"]:
            pair = feb[feb["description"] == desc]["account"]
            assert "預金" in set(pair), f"{acc} の2月の仕訳が預金を通っていない"
    after = upto(df, y1 + 1, 2)
    for acc in ("未払消費税", "未払所得税（法人税）", "未収還付消費税"):
        assert abs(cr(after, acc) - dr(after, acc)) < 1.0, f"2月末に {acc} が残っている"


# ------------------------------------------------------------
# OD-07 / OD-08
# ------------------------------------------------------------
@pytest.mark.parametrize("factory", [params_always_short, params_dip_and_recover, params_exit_short])
def test_exit_month(factory):
    p = factory()
    df = run(p)
    exit_cal = p.start_date.year + p.exit_params.exit_year - 1
    dec = month_df(df, exit_cal, 12)
    assert cr(dec, OD) == 0, "売却月に新たに借りている"
    assert abs(od_balance(df)) < 1.0, "売却後に借越が残っている"
    assert deposit(df) > -1.0
    # 借越の返済は預金から（元入金への直接振替はない）
    bad = df[(df["description"].str.contains("最終精算", na=False))]
    assert bad.empty, f"元入金への最終精算仕訳が残っている：{set(bad['account'])}"


def test_exit_repaid_from_deposit(df_short):
    p = params_always_short()
    exit_cal = p.start_date.year + p.exit_params.exit_year - 1
    dec = month_df(df_short, exit_cal, 12)
    assert dr(dec, OD) > 0, "売却月に借越を返していない"
    assert df_short[df_short["description"] == "出口月の預金不足分"].empty, \
        "売却代金で足りるのに元入金を入れている"


def test_exit_shortfall_filled_by_capital():
    p = params_exit_short()
    df = run(p)
    inj = df[df["description"] == "出口月の預金不足分"]
    assert not inj.empty, "預金が足りないのに元入金で埋めていない"
    assert set(inj["account"]) == {"預金", "元入金"}
    assert abs(deposit(df)) < 1.0, "不足を埋めたあとの預金は 0 になるはず"
    assert abs(od_balance(df)) < 1.0


def test_exit_year_taxes_paid_in_cash():
    p = dataclasses.replace(make_minimal_params(exit_year=3), overdraft_interest_rate=RATE)
    sim = Simulation(p, p.start_date)
    sim.run()
    taxes = {"未払消費税", "未払所得税（法人税）", "未収還付消費税"}
    for e in sim.ledger.entries:
        if e.dr_account in taxes or e.cr_account in taxes:
            assert "元入金" not in (e.dr_account, e.cr_account), \
                f"{e.date} {e.dr_account}／{e.cr_account} が元入金への振替になっている"
    df = sim.ledger.get_df()
    for acc in taxes:
        assert abs(cr(df, acc) - dr(df, acc)) < 1.0, f"売却後に {acc} が残っている"
    exit_cal = p.start_date.year + p.exit_params.exit_year - 1
    paid = df[df["description"].str.endswith("（出口）", na=False)
              & (df["year"] == exit_cal)]
    assert not paid.empty, "出口の年の税金を売却月に払っていない"


# ------------------------------------------------------------
# OD-09
# ------------------------------------------------------------
@pytest.mark.parametrize("name", ["df_short", "df_dip"])
def test_each_month_balanced(name, request):
    df = request.getfixturevalue(name)
    for y, m in month_keys(df):
        mdf = month_df(df, y, m)
        d = mdf[mdf["dr_cr"] == "debit"]["amount"].sum()
        c = mdf[mdf["dr_cr"] == "credit"]["amount"].sum()
        assert abs(d - c) < 1.0, f"{y}-{m:02d} 貸借不一致"


# ------------------------------------------------------------
# OD-10 / OD-11 / OD-12
# ------------------------------------------------------------
def test_limit_exceeded_raises():
    with pytest.raises(ValueError, match="当座借越"):
        run(params_always_short(overdraft_limit=100_000))


def test_limit_not_exceeded_runs():
    run(params_always_short(overdraft_limit=100_000_000))


def test_disabled_makes_no_overdraft_entries():
    df = run(params_always_short(overdraft_enabled=False))
    assert cr(df, OD) == 0 and dr(df, OD_INT) == 0


def test_negative_rate_raises():
    p = dataclasses.replace(make_minimal_params(), overdraft_interest_rate=-0.01)
    with pytest.raises(ValueError):
        run(p)
