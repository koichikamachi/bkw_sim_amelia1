# ================================
# core/tax/tax_splitter.py
# 仕様書 第7章 消費税分解ロジック 準拠版
# ================================
#
# 【設計思想】
#   日本の仕入税額控除（課税売上割合按分）に基づき、
#   税込金額を以下の3要素に分解する：
#
#     tax_base          : 税抜本体（費用または資産の取得原価）
#     vat_deductible    : 控除可能消費税（→ 仮払消費税）
#     vat_nondeductible : 控除不能消費税（→ 租税公課（消費税）または原価算入）
#
# 【計算式】
#   税抜本体      = 税込総額 ÷ (1 + 消費税率)
#   消費税合計    = 税込総額 - 税抜本体
#   控除可能VAT   = 消費税合計 × 課税売上割合（= 1 - 非課税割合）
#   控除不能VAT   = 消費税合計 × 非課税割合
#
# 【重要：旧実装の誤り】
#   旧コードは税込総額を課税部分・非課税部分に分割してから
#   それぞれに消費税計算を適用していたため、
#   非課税部分に消費税がかからないという誤った前提になっていた。
#   正しくは「購入金額全体に消費税がかかり、控除できる割合が
#   課税売上割合で按分される」。
#
# ================================

import math as _math


def split_vat(
    gross_amount: float,
    vat_rate: float,
    non_taxable_ratio: float,
    rounding: str = "round",   # "round" / "floor" / "ceil"
) -> dict:
    """
    税込金額を税抜本体・控除可能VAT・控除不能VATに分解する。

    Parameters
    ----------
    gross_amount      : 税込金額
    vat_rate          : 消費税率（例：0.10 = 10%）
    non_taxable_ratio : 非課税売上割合（例：0.40 = 40%）
    rounding          : 端数処理方式（デフォルト：四捨五入）

    Returns
    -------
    dict with keys:
        tax_base          : float  税抜本体
        vat_deductible    : float  控除可能消費税（仮払消費税へ）
        vat_nondeductible : float  控除不能消費税（租税公課または原価算入）
    """
    if gross_amount <= 0:
        return {
            "tax_base":          0.0,
            "vat_deductible":    0.0,
            "vat_nondeductible": 0.0,
        }

    # 端数処理関数
    def apply_round(x: float) -> float:
        if rounding == "floor":
            return float(int(x))
        elif rounding == "ceil":
            return float(_math.ceil(x))
        else:  # "round"（デフォルト）
            return float(round(x))

    # -------------------------------------------------------
    # Step 1: 税抜本体と消費税合計を計算
    # -------------------------------------------------------
    if vat_rate > 0:
        tax_base_raw  = gross_amount / (1.0 + vat_rate)
        vat_total_raw = gross_amount - tax_base_raw
    else:
        # 消費税率ゼロ（免税事業者相当）
        tax_base_raw  = gross_amount
        vat_total_raw = 0.0

    # -------------------------------------------------------
    # Step 2: 消費税を課税売上割合で按分
    #   控除可能   = 消費税合計 × (1 - 非課税割合)
    #   控除不能   = 消費税合計 ×   非課税割合
    # -------------------------------------------------------
    taxable_ratio     = 1.0 - non_taxable_ratio
    vat_deductible_raw    = vat_total_raw * taxable_ratio
    vat_nondeductible_raw = vat_total_raw * non_taxable_ratio

    # -------------------------------------------------------
    # Step 3: 丸め処理
    #   丸め誤差が生じないよう、最後に合計を調整する。
    #   tax_base = gross - vat_deductible - vat_nondeductible
    # -------------------------------------------------------
    vat_d  = apply_round(vat_deductible_raw)
    vat_nd = apply_round(vat_nondeductible_raw)
    # 税抜本体は残差として計算（合計が gross と一致することを保証）
    tax_base = apply_round(gross_amount - vat_d - vat_nd)

    return {
        "tax_base":          tax_base,
        "vat_deductible":    vat_d,
        "vat_nondeductible": vat_nd,
    }

# ================================
# core/tax/tax_splitter.py end
# ================================