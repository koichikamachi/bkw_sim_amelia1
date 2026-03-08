"""
CF差異診断スクリプト
実行: python diagnose_cf.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.params import SimulationParams, LoanParams, ExitParams
from core.simulation.simulation import Simulation
from core.finance.fs_builder import FinancialStatementBuilder
import datetime

# テストC-07と同じパラメータ
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
df = sim.ledger.get_df()
fs_builder = FinancialStatementBuilder(sim.ledger)
fs = fs_builder.build()

years = sorted(df["year"].dropna().unique().astype(int))

print("=" * 70)
print("【預金の年次増減】")
for y in years:
    ydf = df[df["year"] == y]
    dr = ydf[ydf["account"] == "預金"][ydf["dr_cr"] == "debit"]["amount"].sum()
    cr = ydf[ydf["account"] == "預金"][ydf["dr_cr"] == "credit"]["amount"].sum()
    print(f"  Year {y}: 借方={dr:>15,.0f}  貸方={cr:>15,.0f}  純増減={dr-cr:>15,.0f}")

total_dr = df[df["account"] == "預金"][df["dr_cr"] == "debit"]["amount"].sum()
total_cr = df[df["account"] == "預金"][df["dr_cr"] == "credit"]["amount"].sum()
cash_net = total_dr - total_cr
print(f"  合計:        借方={total_dr:>15,.0f}  貸方={total_cr:>15,.0f}  純増減={cash_net:>15,.0f}")

print()
print("【CFの資金収支尻】")
cf_df = fs["cf"]
year_cols = [f"Year {y}" for y in years]
for col in year_cols:
    print(f"  {col}: {cf_df.loc['【資金収支尻】', col]:>15,.0f}")
cf_total = cf_df.loc["【資金収支尻】", year_cols].sum()
print(f"  合計:  {cf_total:>15,.0f}")

print()
print(f"【差額】 預金純増減={cash_net:,.0f}  CF合計={cf_total:,.0f}  差={cash_net - cf_total:,.0f}")

print()
print("=" * 70)
print("【CF詳細（年次）】")
for row in cf_df.index:
    vals = [cf_df.loc[row, col] for col in year_cols]
    total = sum(vals)
    if total != 0 or row.startswith("【"):
        print(f"  {row:30s} " + "  ".join(f"{v:>12,.0f}" for v in vals) + f"  合計={total:>12,.0f}")

print()
print("=" * 70)
print("【Year1の預金仕訳（取得フェーズ含む全件）- 相手科目別集計】")
y1_cash = df[(df["year"] == years[0]) & (df["account"] == "預金")]
print("  借方（預金増加）の相手科目:")
# 同じidの反対側を探す
for _, row in y1_cash[y1_cash["dr_cr"] == "debit"].groupby("account").head(0).iterrows():
    pass
# idペアで相手科目を探す
all_cash_ids = y1_cash["id"].unique()
y1_all = df[df["year"] == years[0]]
pairs_dr = {}
pairs_cr = {}
for eid in all_cash_ids:
    pair = y1_all[y1_all["id"] == eid]
    cash_row = pair[pair["account"] == "預金"]
    other_row = pair[pair["account"] != "預金"]
    if cash_row.empty or other_row.empty:
        continue
    for _, cr_row in cash_row.iterrows():
        for _, ot_row in other_row.iterrows():
            acc = ot_row["account"]
            amt = cr_row["amount"]
            if cr_row["dr_cr"] == "debit":
                pairs_dr[acc] = pairs_dr.get(acc, 0) + amt
            else:
                pairs_cr[acc] = pairs_cr.get(acc, 0) + amt

print("  借方（預金増加）の相手科目別:")
for acc, amt in sorted(pairs_dr.items(), key=lambda x: -x[1]):
    print(f"    {acc:30s}: {amt:>12,.0f}")
print("  貸方（預金減少）の相手科目別:")
for acc, amt in sorted(pairs_cr.items(), key=lambda x: -x[1]):
    print(f"    {acc:30s}: {amt:>12,.0f}")

print()
print("【Exit年(Year3)の12/31付け預金仕訳】")
exit_y = max(years)
exit_cash = df[
    (df["year"] == exit_y) &
    (df["date"].astype(str).str.endswith("-12-31")) &
    (df["account"] == "預金")
]
for _, row in exit_cash.iterrows():
    print(f"  {row['dr_cr']:6s}  {row['amount']:>12,.0f}")
