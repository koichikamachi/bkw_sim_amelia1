# ============================================
# core/bookkeeping/tax_utils.py
# （消費税のユーティリティ：税込→税抜、控除不能消費税の計算）
# ============================================

class TaxUtils:
    """
    TaxUtils
    -----------------------------
    ・税込金額 → 税抜金額・消費税額 に分解
    ・課税売上割合を考慮した「控除可能税額」と「控除不能税額」の計算
    ・初期投資／追加設備／運営費用／売却費用など全てで利用する前提
    """

    def __init__(self, tax_rate: float, taxable_ratio: float):
        """
        Parameters
        ----------
        tax_rate : float
            例：0.10（10%）
        taxable_ratio : float
            課税売上割合（例：0.3 なら 30%）
            → 控除可能税額 = tax_amount * taxable_ratio
        """
        self.tax_rate = tax_rate
        self.taxable_ratio = taxable_ratio

    # -------------------------------------------------------
    # ★1：税込金額を税抜＋税額に分解
    # -------------------------------------------------------
    def split_tax(self, gross_amount: float) -> tuple:
        """
        税込金額 → (税抜金額, 消費税額) を返す。
        ※ 税抜 = gross / (1 + 税率)
        """
        if gross_amount == 0:
            return 0.0, 0.0

        net = gross_amount / (1 + self.tax_rate)
        tax = gross_amount - net
        return net, tax

    # -------------------------------------------------------
    # ★2：控除可能税額／控除不能税額 の分解
    # -------------------------------------------------------
    def allocate_tax(self, tax_amount: float) -> tuple:
        """
        消費税額 → (控除可能, 控除不能) に分ける。

        控除可能：tax_amount * 課税売上割合
        控除不能：残り（＝費用へ算入）

        Returns
        -------
        (deductible, nondeductible)
        """
        if tax_amount == 0:
            return 0.0, 0.0

        deductible = tax_amount * self.taxable_ratio
        nondeductible = tax_amount - deductible
        return deductible, nondeductible

    # -------------------------------------------------------
    # ★3：税込金額 → 税抜・控除可能・控除不能 を一括計算
    # -------------------------------------------------------
    def split_and_allocate(self, gross_amount: float) -> tuple:
        """
        税込金額を以下へ一度に分解する：

        ・税抜金額 net
        ・控除可能税額 tax_deduct
        ・控除不能税額 tax_non_deduct

        例：
            net, d, nd = tax.split_and_allocate(gross)
        """
        net, tax = self.split_tax(gross_amount)
        tax_deduct, tax_non_deduct = self.allocate_tax(tax)
        return net, tax_deduct, tax_non_deduct


# ============================================
# END core/bookkeeping/tax_utils.py
# ============================================