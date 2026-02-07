# ================================
# core/tax/tax_splitter.py（完全修正版）
# ================================

def split_vat(
    gross_amount: float,
    vat_rate: float,
    non_taxable_ratio: float,
    rounding: str = "round"  # "round" / "floor" / "ceil" に対応可能
) -> dict:

    if gross_amount <= 0:
        return {
            "tax_base": 0.0,
            "vat_deductible": 0.0,
            "vat_nondeductible": 0.0,
        }

    taxable_ratio = 1.0 - non_taxable_ratio
    nontax_ratio = non_taxable_ratio

    taxable_gross = gross_amount * taxable_ratio
    nontax_gross   = gross_amount * nontax_ratio

    # 税抜抽出
    tax_base_taxable = taxable_gross / (1 + vat_rate)
    vat_deductible   = taxable_gross - tax_base_taxable

    # 非課税部分＝そのまま
    tax_base_nontax = nontax_gross
    vat_nondeductible = 0.0

    # ---- 丸め関数を選択 ----
    def apply_round(x):
        if rounding == "floor":
            return int(x)
        elif rounding == "ceil":
            import math
            return math.ceil(x)
        else:  # "round"
            return round(x)

    return {
        "tax_base": apply_round(tax_base_taxable + tax_base_nontax),
        "vat_deductible": apply_round(vat_deductible),
        "vat_nondeductible": apply_round(vat_nondeductible),
    }