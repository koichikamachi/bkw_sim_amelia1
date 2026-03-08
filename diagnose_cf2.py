"""
CF差異診断スクリプト v2
実行: python diagnose_cf2.py
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
fs_builder = FinancialStatementBuilder(sim.ledger)
fs = fs_builder.build()

years = sorted(df["year"].dropna().unique().astype(int))
year_cols = [f"Year {y}" for y in years]

# =========================================================
# 1. 年次別 預金純増減 vs CF収支尻
# =========================================================
print("=" * 70)
print("【年次別: 預金純増減 vs CF収支尻】")
print(f"  {'Year':>6}  {'預金借方':>14}  {'預金貸方':>14}  {'預金純増減':>14}  {'CF収支尻':>14}  {'差異':>12}")
total_diff = 0
for y in years:
    col = f"Year {y}"
    ydf = df[df["year"] == y]
    dr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "debit")]["amount"].sum())
    cr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "credit")]["amount"].sum())
    net = dr - cr
    cf_val = float(fs["cf"].loc["【資金収支尻】", col])
    diff = net - cf_val
    total_diff += diff
    print(f"  {y:>6}  {dr:>14,.0f}  {cr:>14,.0f}  {net:>14,.0f}  {cf_val:>14,.0f}  {diff:>12,.0f}")

all_dr = float(df[(df["account"] == "預金") & (df["dr_cr"] == "debit")]["amount"].sum())
all_cr = float(df[(df["account"] == "預金") & (df["dr_cr"] == "credit")]["amount"].sum())
cf_sum = float(fs["cf"].loc["【資金収支尻】", year_cols].sum())
print(f"  {'合計':>6}  {all_dr:>14,.0f}  {all_cr:>14,.0f}  {all_dr-all_cr:>14,.0f}  {cf_sum:>14,.0f}  {all_dr-all_cr-cf_sum:>12,.0f}")

# =========================================================
# 2. 年次別: 預金の相手科目別増減
# =========================================================
print()
print("=" * 70)
print("【年次別: 預金増減の相手科目別集計】")

for y in years:
    print(f"\n  --- Year {y} ---")
    ydf = df[df["year"] == y].copy()

    # id別に相手科目を特定
    cash_ids = ydf[ydf["account"] == "預金"]["id"].unique()
    pairs_dr = {}   # 預金が借方（収入）のとき相手は貸方
    pairs_cr = {}   # 預金が貸方（支出）のとき相手は借方

    for eid in cash_ids:
        pair = ydf[ydf["id"] == eid]
        cash_row = pair[pair["account"] == "預金"]
        other_rows = pair[pair["account"] != "預金"]
        if cash_row.empty or other_rows.empty:
            continue
        for _, crow in cash_row.iterrows():
            for _, orow in other_rows.iterrows():
                acc = orow["account"]
                amt = float(orow["amount"])
                if crow["dr_cr"] == "debit":
                    pairs_dr[acc] = pairs_dr.get(acc, 0.0) + amt
                else:
                    pairs_cr[acc] = pairs_cr.get(acc, 0.0) + amt

    print(f"  預金収入（借方）相手科目:")
    for acc, amt in sorted(pairs_dr.items(), key=lambda x: -x[1]):
        print(f"    {acc:30s}: {amt:>12,.0f}")
    print(f"  預金支出（貸方）相手科目:")
    for acc, amt in sorted(pairs_cr.items(), key=lambda x: -x[1]):
        print(f"    {acc:30s}: {amt:>12,.0f}")

# =========================================================
# 3. CF詳細
# =========================================================
print()
print("=" * 70)
print("【CF詳細】")
cf_df = fs["cf"]
print(f"  {'科目':30s}" + "  ".join(f"  {c:>12}" for c in year_cols) + f"  {'合計':>12}")
for row in cf_df.index:
    vals = [float(cf_df.loc[row, col]) for col in year_cols]
    total = sum(vals)
    if total != 0 or row.startswith("【"):
        print(f"  {row:30s}" + "  ".join(f"  {v:>12,.0f}" for v in vals) + f"  {total:>12,.0f}")

# =========================================================
# 4. 仮払消費税の年次別借方合計
# =========================================================
print()
print("=" * 70)
print("【仮払消費税 借方合計（現金支出分の内訳）】")
for y in years:
    ydf = df[df["year"] == y]
    vat_dr = float(ydf[(ydf["account"] == "仮払消費税") & (ydf["dr_cr"] == "debit")]["amount"].sum())
    vat_cr = float(ydf[(ydf["account"] == "仮払消費税") & (ydf["dr_cr"] == "credit")]["amount"].sum())
    # 12/31付け（年末精算=非現金）を除いた借方
    if "date" in ydf.columns:
        vat_dr_cash = float(
            ydf[
                (ydf["account"] == "仮払消費税") &
                (ydf["dr_cr"] == "debit") &
                ~(ydf["date"].astype(str).str.endswith("-12-31"))
            ]["amount"].sum()
        )
    else:
        vat_dr_cash = vat_dr
    print(f"  Year {y}: 借方合計={vat_dr:>10,.0f}  うち現金支出分(12/31除く)={vat_dr_cash:>10,.0f}  貸方合計(精算)={vat_cr:>10,.0f}")
