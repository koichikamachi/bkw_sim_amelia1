# ============================================================
# core/tax/periodic_expense_vat_builder.py（JournalEntry対応版）
# ============================================================

from core.ledger.journal_entry import make_entry_pair
from core.tax.tax_splitter import split_vat

def build_periodic_expense_entries(
    date,
    account_name: str,
    gross_amount: float,
    vat_rate: float,
    non_taxable_ratio: float
):
    """
    定期費用（管理費・修繕費など）を VAT 分解して
    JournalEntry のリストとして返す。

    ・税抜本体＋控除不能VAT → 費用計上
    ・控除可能VAT → 仮払消費税
    ・支払額 → 現金（または預金）
    """

    entries = []

    # VAT 分解
    taxinfo = split_vat(
        gross_amount=gross_amount,
        vat_rate=vat_rate,
        non_taxable_ratio=non_taxable_ratio
    )

    base = taxinfo["tax_base"]
    vat_deductible = taxinfo["vat_deductible"]      # 控除可能VAT
    vat_nondeductible = taxinfo["vat_nondeductible"] # 控除不能VAT

    # 1) 税抜本体＋控除不能VAT → 費用計上（借方）
    expense_amount = base + vat_nondeductible
    if expense_amount > 0:
        entries += make_entry_pair(
            date=date,
            debit_account=account_name,
            credit_account="預金",
            amount=expense_amount
        )

    # 2) 控除可能VAT → 仮払消費税
    if vat_deductible > 0:
        entries += make_entry_pair(
            date=date,
            debit_account="仮払消費税",
            credit_account="預金",
            amount=vat_deductible
        )

    return entries

# ============================================================
# END
# ============================================================