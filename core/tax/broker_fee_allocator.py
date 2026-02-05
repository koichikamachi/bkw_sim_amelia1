# ===========================================
# core/tax/broker_fee_allocator.py  修正版
# ===========================================

from .tax_splitter import split_vat

def allocate_broker_fee(
    gross_broker_fee: float,
    land_net: float,
    building_net: float,
    vat_rate: float,
    non_taxable_ratio: float,
    rounding: str = "floor"
):
    """
    仲介手数料（税込）を
        土地：税抜按分
        建物：税抜按分
        VAT（控除可/不可）：用途比率で按分
    に正確に配分する。
    """

    if gross_broker_fee <= 0:
        return {
            "land_cost_addition": 0,
            "building_cost_addition": 0,
            "vat_deductible": 0,
            "vat_nondeductible": 0,
        }

    # 1) 税抜 + VAT に分離（split_vat は用途比率考慮済）
    fee_split = split_vat(
        gross_amount=gross_broker_fee,
        vat_rate=vat_rate,
        non_taxable_ratio=non_taxable_ratio,
        rounding=rounding,
    )

    fee_base = fee_split["tax_base"]
    vat_deductible = fee_split["vat_deductible"]
    vat_nondeductible = fee_split["vat_nondeductible"]  # 今は常に0だが構造は維持

    # 2) 税抜部分 → 土地：建物へ按分（価額比）
    total_net = land_net + building_net
    if total_net > 0:
        land_ratio = land_net / total_net
        bld_ratio = building_net / total_net
    else:
        land_ratio = bld_ratio = 0.5

    land_cost_addition = fee_base * land_ratio
    building_cost_addition = fee_base * bld_ratio

    # 3) VAT の扱い
    #    ・控除可 VAT → 仮払消費税として ledger 登録される（建物側）
    #    ・控除不可 VAT（nondeductible）→ 建物原価に加算
    building_cost_addition += vat_nondeductible

    return {
        "land_cost_addition": int(land_cost_addition),
        "building_cost_addition": int(building_cost_addition),
        "vat_deductible": int(vat_deductible),
        "vat_nondeductible": int(vat_nondeductible),
    }