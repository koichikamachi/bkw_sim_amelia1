# BKW Invest Sim（Amelia v4）

**簿記エンジン型 不動産投資シミュレーター**  
Bookkeeping-Driven Real Estate Investment Simulator

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bkwsimamelia1-8tkbymyebhfaakmybwwea7.streamlit.app/)

---

## 日本語

### 概要

BKW Invest Sim は、**簿記エンジンに基づく不動産投資シミュレーター**です。

一般的な投資計算ツールが単純な計算式によって結果を求めるのに対し、本システムでは実際の会計処理の流れを再現します。

```
会計取引 → 総勘定元帳 → 財務諸表（BS・PL・CF）
```

この構造を通じて、投資のキャッシュフローや資金収支を分析します。減価償却・消費税処理・借入返済・売却損益といった複雑な要素を会計的に正確にシミュレートすることで、投資の経済的実態をより正確に把握できるよう設計されています。

---

### コンセプト

多くの不動産投資ツールは、次のような単純計算に依存しています。

```
家賃 − 経費 − ローン返済 ＝ キャッシュフロー
```

しかし実際の投資成果は、以下のような複雑な要素によって決まります。

- 減価償却（残存耐用年数・月割）
- 消費税処理（課税売上割合・仮払・仮受・精算）
- 融資構造（元利均等返済・当座借越）
- 会計処理（税抜経理・複式簿記）
- 売却シナリオ（固定資産売却仮勘定・売却損益）
- 税効果（所得税・法人税・繰延課税）

BKW Invest Sim はこれらを**複式簿記エンジンによって完全に再現**します。

---

### 主な機能

- 複式簿記に基づく投資シミュレーション（日本の会計基準準拠）
- 会計仕訳の自動生成（取得・月次・期末・売却）
- 総勘定元帳の生成・閲覧
- 財務諸表の生成（貸借対照表・損益計算書・資金収支CF）
- DCF分析（PV・I₀・NPV）および投資利回り算出
- Excelファイル出力（仕訳帳・財務諸表・入力条件サマリー）

---

### デモ

Streamlit アプリ（無料・ブラウザから即時利用可）

🔗 https://bkwsimamelia1-8tkbymyebhfaakmybwwea7.streamlit.app/

---

### 動作要件

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

**必要パッケージ：** `streamlit` `pandas` `numpy` `openpyxl`

---

### ライセンス

MIT License

---

## English

### Overview

BKW Invest Sim is a **bookkeeping-driven real estate investment simulator**.

Unlike typical investment calculators that rely on simplified formulas, this system reproduces the actual accounting process of an investment project.

```
Accounting Transaction → General Ledger → Financial Statements (BS / PL / CF)
```

By simulating the full accounting workflow, the system enables accurate analysis of investment cash flows and financial performance. Complex factors such as depreciation, consumption tax treatment, loan repayment, and exit gains/losses are handled with full accounting precision.

---

### Concept

Most real estate investment tools follow a simplified model:

```
rent − expenses − loan payment = cash flow
```

However, real investment outcomes are shaped by more complex factors:

- Depreciation (remaining useful life, monthly proration)
- Consumption tax treatment (taxable ratio, input/output tax, year-end settlement)
- Financing structure (annuity repayment, overdraft)
- Accounting treatment (tax-exclusive bookkeeping, double-entry)
- Exit scenario (disposal account method, gain/loss on sale)
- Tax effects (income tax, corporate tax, deferred taxation)

BKW Invest Sim reconstructs all of these through a **full double-entry bookkeeping engine**.

---

### Features

- Double-entry bookkeeping simulation compliant with Japanese accounting standards
- Automatic generation of journal entries (acquisition, monthly, year-end, exit)
- General ledger construction and browsing
- Financial statement generation (Balance Sheet, Income Statement, Cash Flow)
- DCF analysis (PV, I₀, NPV) and investment return calculations
- Excel export (journal, financial statements, input summary)

---

### Demo

Streamlit app (free, runs in browser)

🔗 https://bkwsimamelia1-8tkbymyebhfaakmybwwea7.streamlit.app/

---

### Requirements

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

**Dependencies:** `streamlit` `pandas` `numpy` `openpyxl`

---

### License

MIT License

---

## Author

**Koichi Kamachi, CPA (Japan)**  
Bookkeeping Whisperer Project

A financial simulation tool for real estate investment, developed by Koichi Kamachi, CPA. This application models cash flow, financing structure, consumption tax effects, and exit scenarios for Japanese real estate investment, based on double-entry bookkeeping principles.

- Excel prototype development support: Taichiro Mochizuki (Real Estate Appraiser, Japan)
- Python implementation: Koichi Kamachi, with AI development assistance
