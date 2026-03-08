"""
残差663,947の診断スクリプト
実行: python diagnose_cf3.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.params import SimulationParams, LoanParams, ExitParams
from core.simulation.simulation import Simulation
from core.finance.fs_builder import FinancialStatementBuilder
import datetime
import pandas as pd

params = SimulationParams(
    property_price_building=50_000_000.0,
    property_price_land=30_000_000.0,
    brokerage_fee_amount_incl=1_650_000.0,
    building_useful_life=47,
    building_age=0,
    holding_years=3,
    initial_loan=LoanParams(30_000_000, 0.025, 20, "annuity"),
    initial_equity=53_650_000.0,
    rent_setting_mode="AMOUNT",
    target_cap_rate=0.0,
    annual_rent_income_incl=2_400_000.0,
    annual_management_fee_initial=240_000.0,
    repair_cost_annual=120_000.0,
    insurance_cost_annual=60_000.0,
    fixed_asset_tax_land=80_000.0,
    fixed_asset_tax_building=120_000.0,
    other_management_fee_annual=0.0,
    management_fee_rate=0.0,
    consumption_tax_rate=0.10,
    non_taxable_proportion=0.40,
    overdraft_interest_rate=0.05,
    cf_discount_rate=0.0,
    exit_params=ExitParams(
        exit_year=3,
        land_exit_price=30_000_000.0,
        building_exit_price=30_000_000.0,
        exit_cost=1_000_000.0,
    ),
    additional_investments=[],
    start_date=datetime.date(2025, 1, 1),
    entity_type="individual",
    income_tax_rate=0.20,
    corporate_tax_rate=0.0,
)

sim = Simulation(params, params.start_date)
sim.run()
df = sim.ledger.get_df().copy()
df["parsed_date"] = pd.to_datetime(df["date"])
df["is_year_end"] = (df["parsed_date"].dt.month == 12) & (df["parsed_date"].dt.day == 31)
fs_builder = FinancialStatementBuilder(sim.ledger)
fs = fs_builder.build()

years = sorted(df["year"].dropna().unique().astype(int))
year_cols = [f"Year {y}" for y in years]

print("=" * 70)
print("【年次別 差異】")
for y in years:
    col = f"Year {y}"
    ydf = df[df["year"] == y]
    dr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "debit")]["amount"].sum())
    cr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "credit")]["amount"].sum())
    net = dr - cr
    cf_val = float(fs["cf"].loc["【資金収支尻】", col])
    print(f"  Year {y}: 預金純増減={net:>12,.0f}  CF={cf_val:>12,.0f}  差={net-cf_val:>10,.0f}")

print()
print("=" * 70)
print("【預金の全相手科目別集計（年次・DR/CR別）】")
for y in years:
    print(f"\n  --- Year {y} ---")
    ydf = df[df["year"] == y].copy()
    cash_ids = ydf[ydf["account"] == "預金"]["id"].unique()

    pairs_dr = {}
    pairs_cr = {}
    for eid in cash_ids:
        pair = ydf[ydf["id"] == eid]
        cash_rows = pair[pair["account"] == "預金"]
        other_rows = pair[pair["account"] != "預金"]
        if cash_rows.empty or other_rows.empty:
            continue
        for _, crow in cash_rows.iterrows():
            for _, orow in other_rows.iterrows():
                acc = orow["account"]
                amt = float(crow["amount"])
                is_ye = bool(crow["is_year_end"])
                key = f"{acc} {'[12/31]' if is_ye else ''}"
                if crow["dr_cr"] == "debit":
                    pairs_dr[key] = pairs_dr.get(key, 0.0) + amt
                else:
                    pairs_cr[key] = pairs_cr.get(key, 0.0) + amt

    print("  預金借方（収入）:")
    for k, v in sorted(pairs_dr.items(), key=lambda x: -x[1]):
        print(f"    {k:40s}: {v:>12,.0f}")
    print("  預金貸方（支出）:")
    for k, v in sorted(pairs_cr.items(), key=lambda x: -x[1]):
        print(f"    {k:40s}: {v:>12,.0f}")

print()
print("=" * 70)
print("【CF詳細】")
cf_df = fs["cf"]
for row in cf_df.index:
    vals = [float(cf_df.loc[row, col]) for col in year_cols]
    total = sum(vals)
    if total != 0 or row.startswith("【"):
        print(f"  {row:30s}" + "  ".join(f"  {v:>12,.0f}" for v in vals) + f"  合計={total:>12,.0f}")
