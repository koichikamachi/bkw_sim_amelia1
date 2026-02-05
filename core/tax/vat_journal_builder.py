# ===============================================
# core/tax/vat_journal_builder.py
# ===============================================
from core.ledger.journal_entry import make_entry_pair

def build_vat_journal_entries(
    date,
    base_account: str,
    counter_account: str,
    tax_info: dict,
    is_sale: bool = False
):
    """
    共通 VAT 仕訳ビルダー（レンガ③）
    --------------------------------------
    tax_info には split_vat の結果を入れる：
        {
            "tax_base": 税抜本体,
            "vat_deductible": 控除可能VAT,
            "vat_nondeductible": 控除不能VAT
        }

    is_sale:
        False → 仕入（仮払消費税）
        True  → 売上（仮受消費税）
    """

    entries = []

    tax_base = tax_info["tax_base"]
    vat_deductible = tax_info["vat_deductible"]
    vat_nondeductible = tax_info["vat_nondeductible"]

    # -------------------------
    # ① 税抜本体の仕訳
    # -------------------------
    entries.append(
        make_entry_pair(date, base_account, counter_account, tax_base)
    )

    # -------------------------
    # ② 控除可能 VAT（仮払 / 仮受）
    # -------------------------
    if vat_deductible > 0:
        vat_account = "仮受消費税" if is_sale else "仮払消費税"
        entries.append(
            make_entry_pair(date, vat_account, counter_account, vat_deductible)
        )

    # -------------------------
    # ③ 控除不能 VAT（仕入側）
    #    → 基本科目に加算（費用原価化）
    # -------------------------
    if vat_nondeductible > 0:
        # 建物 などの原価計上 or 販売費及一般管理費 etc.
        entries.append(
            make_entry_pair(date, base_account, counter_account, vat_nondeductible)
        )

    return entries

# core/tax/vat_journal_builder.py　end
