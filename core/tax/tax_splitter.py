# ================================
# core/tax/tax_splitter.py  修正版
# ================================

def split_vat(
    gross_amount: float,
    vat_rate: float,
    non_taxable_ratio: float,
    rounding: str = "floor"
) -> dict:
    """
    税込金額を
      ① 税抜本体
      ② 控除可能仮払消費税（課税売上対応部分）
      ③ 控除不能消費税（非課税売上対応部分：原価算入）
    に分離する。
    """

    if gross_amount <= 0:
        return {
            "tax_base": 0.0,
            "vat_deductible": 0.0,
            "vat_nondeductible": 0.0,
        }

    taxable_ratio = 1.0 - non_taxable_ratio  # 事務所用途など課税売上対応
    nontax_ratio = non_taxable_ratio         # 住居用途など非課税売上対応

    # 1) 税込額を用途比率で分割
    taxable_gross = gross_amount * taxable_ratio
    nontax_gross = gross_amount * nontax_ratio

    # 2) 課税部分：税込→税抜
    tax_base_taxable = taxable_gross / (1 + vat_rate)
    vat_deductible = taxable_gross - tax_base_taxable  # → 仮払消費税

    # 3) 非課税部分：税込＝税抜、VATなし
    tax_base_nontax = nontax_gross
    vat_nondeductible = 0.0  # 今回は非課税部分は VAT 0 として扱う

    # 端数処理
    def apply_round(x):
        return round(x) if rounding == "round" else int(x)

    return {
        "tax_base": apply_round(tax_base_taxable + tax_base_nontax),
        "vat_deductible": apply_round(vat_deductible),
        "vat_nondeductible": apply_round(vat_nondeductible),
    }