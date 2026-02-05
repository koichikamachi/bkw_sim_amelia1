# ===============================================
# core/tax/brokerage_allocation.py
# ===============================================

def allocate_brokerage(base_amount, building_price, land_price):
    """
    仲介手数料（税抜本体）を建物・土地に按分するレンガ④

    base_amount: 税抜手数料
    building_price: 建物価格（税込または税抜どちらでも比率は同じ）
    land_price: 土地価格
    """
    total = building_price + land_price
    if total <= 0:
        return base_amount, 0  # すべて建物へ（例外ケース）

    building_ratio = building_price / total
    land_ratio = land_price / total

    return (
        base_amount * building_ratio,
        base_amount * land_ratio,
    )

# core/tax/brokerage_allocation.py end
