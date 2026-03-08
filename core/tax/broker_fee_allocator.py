# ===========================================
# core/tax/broker_fee_allocator.py
# 仕様書 第5章 仲介手数料按分ロジック 準拠版
# ===========================================
#
# 【責務】
#   仲介手数料（税込）を以下の4要素に分解して返す。
#   呼び出し元（InitialEntryGenerator）が各要素を ledger に記帳する。
#
#   land_cost_addition    : 土地取得原価への算入額（税抜按分）
#   building_cost_addition: 建物取得原価への算入額（税抜按分）
#   vat_deductible        : 控除可能消費税（→ 仮払消費税）
#   vat_nondeductible     : 控除不能消費税（→ 建物原価算入）
#
# 【重要：責務の分離】
#   vat_nondeductible の建物原価算入は InitialEntryGenerator が行う。
#   本関数は vat_nondeductible を building_cost_addition に加算しない。
#   加算すると呼び出し元でも加算され、二重計上になる。
#
# 【按分方式】
#   税抜手数料本体 → 土地・建物の取得価額比で按分
#   消費税         → split_vat で課税売上割合按分済み
#
# ===========================================

from .tax_splitter import split_vat


def allocate_broker_fee(
    gross_broker_fee: float,
    land_net: float,
    building_net: float,
    vat_rate: float,
    non_taxable_ratio: float,
    rounding: str = "floor",
) -> dict:
    """
    仲介手数料（税込）を土地・建物・VATに按分する。

    Parameters
    ----------
    gross_broker_fee  : 仲介手数料税込総額
    land_net          : 土地取得価額（税抜）← 按分比率の計算に使用
    building_net      : 建物取得価額（税抜）← 按分比率の計算に使用
    vat_rate          : 消費税率（例：0.10）
    non_taxable_ratio : 非課税割合（例：0.40）
    rounding          : 端数処理（"floor" / "round" / "ceil"）

    Returns
    -------
    dict:
        land_cost_addition     : 土地原価算入額（税抜按分）
        building_cost_addition : 建物原価算入額（税抜按分）
                                 ※ vat_nondeductible は含まない
        vat_deductible         : 控除可能VAT（仮払消費税へ）
        vat_nondeductible      : 控除不能VAT（呼び出し元が建物原価に算入）
    """
    if gross_broker_fee <= 0:
        return {
            "land_cost_addition":     0.0,
            "building_cost_addition": 0.0,
            "vat_deductible":         0.0,
            "vat_nondeductible":      0.0,
        }

    # --------------------------------------------------
    # Step 1: 税抜本体・控除可能VAT・控除不能VATに分解
    #         split_vat が課税売上割合按分を処理する
    # --------------------------------------------------
    fee_split = split_vat(
        gross_amount=gross_broker_fee,
        vat_rate=vat_rate,
        non_taxable_ratio=non_taxable_ratio,
        rounding=rounding,
    )
    fee_base          = fee_split["tax_base"]
    vat_deductible    = fee_split["vat_deductible"]
    vat_nondeductible = fee_split["vat_nondeductible"]

    # --------------------------------------------------
    # Step 2: 税抜手数料本体を土地・建物の価額比で按分
    # --------------------------------------------------
    total_net = land_net + building_net
    if total_net > 0:
        land_ratio = land_net / total_net
        bld_ratio  = building_net / total_net
    else:
        # 土地・建物ともゼロの場合は均等按分
        land_ratio = bld_ratio = 0.5

    land_cost_addition     = fee_base * land_ratio
    building_cost_addition = fee_base * bld_ratio

    # --------------------------------------------------
    # Step 3: 返却
    #   ★ vat_nondeductible は building_cost_addition に加算しない。
    #   　 InitialEntryGenerator が受け取って建物原価に算入する。
    #   　 ここで加算すると呼び出し元での加算と合わせて二重計上になる。
    # --------------------------------------------------
    return {
        "land_cost_addition":     float(int(land_cost_addition)),
        "building_cost_addition": float(int(building_cost_addition)),
        "vat_deductible":         float(int(vat_deductible)),
        "vat_nondeductible":      float(int(vat_nondeductible)),
    }

# ===========================================
# core/tax/broker_fee_allocator.py end
# ===========================================