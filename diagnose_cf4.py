"""
make_paramsを直接インポートして診断
実行: python diagnose_cf4.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "tests")))

# テストファイルのmake_paramsとrunを直接使う
from test_integration_cases import make_params, run
from config.params import LoanParams
import pandas as pd

# テストと完全に同じ呼び出し
params = make_params(
    holding_years=3,
    exit_year=3,
    initial_loan=LoanParams(30_000_000, 0.025, 20, "annuity"),
)

print("=== パラメータ確認 ===")
print(f"  initial_equity       = {params.initial_equity:,.0f}")
print(f"  property_price_bld   = {params.property_price_building:,.0f}")
print(f"  property_price_land  = {params.property_price_land:,.0f}")
print(f"  non_taxable_prop     = {params.non_taxable_proportion}")
print(f"  annual_rent_incl     = {params.annual_rent_income_incl:,.0f}")

ledger, fs = run(params)
df = ledger.get_df().copy()
df["parsed_date"] = pd.to_datetime(df["date"])
df["is_year_end"] = (df["parsed_date"].dt.month == 12) & (df["parsed_date"].dt.day == 31)

years = sorted(df["year"].dropna().unique().astype(int))
year_cols = [f"Year {y}" for y in years]

total_cash_dr = float(df[(df["account"] == "預金") & (df["dr_cr"] == "debit")]["amount"].sum())
total_cash_cr = float(df[(df["account"] == "預金") & (df["dr_cr"] == "credit")]["amount"].sum())
cash_net = total_cash_dr - total_cash_cr
cf_total = float(fs["cf"].loc["【資金収支尻】", year_cols].sum())

print()
print("=== 結果 ===")
print(f"  預金純増減  = {cash_net:>14,.0f}")
print(f"  CF合計     = {cf_total:>14,.0f}")
print(f"  差異       = {cash_net - cf_total:>14,.0f}")

print()
print("=== CF詳細 ===")
cf_df = fs["cf"]
for row in cf_df.index:
    vals = [float(cf_df.loc[row, col]) for col in year_cols]
    total = sum(vals)
    if total != 0 or row.startswith("【"):
        print(f"  {row:30s}" + "  ".join(f"{v:>12,.0f}" for v in vals) + f"  合計={total:>12,.0f}")

print()
print("=== 年次別: 預金増減とCF収支尻 ===")
for y in years:
    col = f"Year {y}"
    ydf = df[df["year"] == y]
    dr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "debit")]["amount"].sum())
    cr = float(ydf[(ydf["account"] == "預金") & (ydf["dr_cr"] == "credit")]["amount"].sum())
    net = dr - cr
    cf_val = float(fs["cf"].loc["【資金収支尻】", col])
    print(f"  Year {y}: 預金={net:>12,.0f}  CF={cf_val:>12,.0f}  差={net-cf_val:>10,.0f}")

print()
print("=== 年次別: 仮払消費税内訳 ===")
for y in years:
    ydf = df[df["year"] == y]
    all_dr = float(ydf[(ydf["account"] == "仮払消費税") & (ydf["dr_cr"] == "debit")]["amount"].sum())
    non_ye = float(ydf[(ydf["account"] == "仮払消費税") & (ydf["dr_cr"] == "debit") & ~ydf["is_year_end"]]["amount"].sum())
    ye_only = float(ydf[(ydf["account"] == "仮払消費税") & (ydf["dr_cr"] == "debit") & ydf["is_year_end"]]["amount"].sum())
    print(f"  Year {y}: 全借方={all_dr:>10,.0f}  非12/31={non_ye:>10,.0f}  12/31={ye_only:>10,.0f}")

print()
print("=== 年次別: 仮受消費税内訳 ===")
for y in years:
    ydf = df[df["year"] == y]
    non_ye = float(ydf[(ydf["account"] == "仮受消費税") & (ydf["dr_cr"] == "credit") & ~ydf["is_year_end"]]["amount"].sum())
    ye_only = float(ydf[(ydf["account"] == "仮受消費税") & (ydf["dr_cr"] == "credit") & ydf["is_year_end"]]["amount"].sum())
    print(f"  Year {y}: 非12/31={non_ye:>10,.0f}  12/31={ye_only:>10,.0f}")
