"""Excel 版との突き合わせ用：同じ条件で Python 版を動かし、月ごとの値を JSON で出す。

実行：リポジトリの最上位で  python "docs/2026-11_点検改訂/run_case.py" > py_case.json
例の条件は「突き合わせ表_当座借越_Excel版とPython版.md」の 1 節と同じ。金額の単位は円。
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from config.params import SimulationParams, LoanParams, ExitParams, AdditionalInvestmentParams
from core.simulation.simulation import Simulation

K = 1000  # Excel 版は千円単位

p = SimulationParams(
    property_price_building=60_000 * K,
    property_price_land=10_000 * K,
    brokerage_fee_amount_incl=0,
    building_useful_life=22,
    building_age=0,
    holding_years=5,
    initial_loan=LoanParams(amount=60_000 * K, interest_rate=0.01, years=20, repayment_method="annuity"),
    initial_equity=10_000 * K,
    rent_setting_mode="AMOUNT",
    target_cap_rate=0.0,
    annual_rent_income_incl=9_600 * K,
    annual_management_fee_initial=1_152 * K,   # 家賃 × 12%
    repair_cost_annual=1_200 * K,
    insurance_cost_annual=120 * K,
    fixed_asset_tax_land=600 * K,
    fixed_asset_tax_building=0,
    other_management_fee_annual=240 * K,
    management_fee_rate=0.0,
    consumption_tax_rate=0.10,
    non_taxable_proportion=1.0,
    overdraft_interest_rate=0.03,
    cf_discount_rate=0.0,
    exit_params=ExitParams(exit_year=5, land_exit_price=70_000 * K, building_exit_price=0, exit_cost=0),
    additional_investments=[AdditionalInvestmentParams(
        year=2, amount=10_000 * K, life=10, loan_amount=0, loan_years=1, loan_interest_rate=0.0)],
    start_date=datetime.date(2025, 1, 1),
    entity_type="individual",
    income_tax_rate=0.30,
    corporate_tax_rate=0.0,
)

sim = Simulation(p, p.start_date)
sim.run()
df = sim.ledger.get_df()
df["m"] = (df["year"] - 2025) * 12 + df["month"]

out = {}
for m in range(1, 61):
    mdf = df[df["m"] == m]
    cum = df[df["m"] <= m]

    def s(d, acc, side):
        return float(d[(d["account"] == acc) & (d["dr_cr"] == side)]["amount"].sum())

    out[m] = {
        "od_cr": s(mdf, "当座借越借入金", "credit"),
        "od_dr": s(mdf, "当座借越借入金", "debit"),
        "od_bal": s(cum, "当座借越借入金", "credit") - s(cum, "当座借越借入金", "debit"),
        "int": s(mdf, "当座借越利息", "debit"),
        "dep": s(cum, "預金", "debit") - s(cum, "預金", "credit"),
        "inc_tax_pay": s(mdf, "未払所得税（法人税）", "debit"),
        "tax_calc": s(mdf, "所得税（法人税）", "debit"),
        "exit_inj": float(mdf[mdf["description"] == "出口月の預金不足分"]["amount"].sum()) / 2,
        "bld_dep": s(mdf, "建物減価償却費", "debit"),
        "add_dep": s(mdf, "追加設備減価償却費", "debit"),
        "loan_int": s(mdf, "長期借入金利息", "debit"),
        "loan_prin": s(mdf, "長期借入金", "debit"),
        "gain": s(mdf, "固定資産売却益（損）", "credit") - s(mdf, "固定資産売却益（損）", "debit"),
    }
print(json.dumps(out))

