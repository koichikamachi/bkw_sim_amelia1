# ============================================
# core/finance/fs_mapping.py
# 財務三表の科目分類マスター
# ============================================

# ----------------------------
# 貸借対照表（BS）: 資産
# ----------------------------
BS_ASSETS = {
    "現金": "cash",
    "預金": "cash",
    "土地": "fixed_asset_land",
    "建物": "fixed_asset_building",
    "建物減価償却累計額": "contra_fixed_asset_building",
    "追加設備": "fixed_asset_additional",
    "追加設備減価償却累計額": "contra_fixed_asset_additional",
    "仮払消費税": "tax_receivable",
    "売掛金": "receivable",
}

# ----------------------------
# 貸借対照表（BS）：負債
# ----------------------------
BS_LIABILITIES = {
    "借入金": "loan_payable",
    "初期投資長期借入金": "loan_payable_initial",
    "追加設備長期借入金": "loan_payable_additional",
    "未払消費税": "tax_payable",
    "未払費用": "accrued_expense",
}

# ----------------------------
# 貸借対照表（BS）：純資産
# ----------------------------
BS_EQUITY = {
    "元入金": "capital",
    "繰越利益剰余金": "retained_earnings",
}

# ----------------------------
# 損益計算書（PL）: 収益
# ----------------------------
PL_REVENUE = {
    "売上高": "rent_income",
    "雑収入": "other_income",
}

# ----------------------------
# 損益計算書（PL）：費用
# ----------------------------
PL_EXPENSE = {
    "販売費一般管理費": "sg_a",
    "建物減価償却費": "depr_building",
    "追加設備減価償却費": "depr_additional",
    "支払利息": "interest_expense",
    "租税公課": "tax_expense",
}

# ----------------------------
# キャッシュフロー（CF）
# ----------------------------
# ※「現金（預金）が借方 → 流入」「貸方 → 流出」で判定
CF_MAPPING = {
    # 営業キャッシュフロー（営業CF）
    "売上高": "operating",
    "販売費一般管理費": "operating",
    "建物減価償却費": "operating",
    "追加設備減価償却費": "operating",
    "租税公課": "operating",

    # 投資キャッシュフロー（投資CF）
    "建物": "investing",
    "追加設備": "investing",
    "土地": "investing",

    # 財務キャッシュフロー（財務CF）
    "借入金": "financing",
    "初期投資長期借入金": "financing",
    "追加設備長期借入金": "financing",
    "元入金": "financing",
}