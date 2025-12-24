import sys
import os
import importlib.util

# 1. パス設定（app.pyと同じ条件にする）
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

print("=== 🕵️‍♀️ アメリアの現場検証レポート ===")
print(f"現在地 (CWD): {os.getcwd()}")
print(f"検索パス (sys.path[0]): {sys.path[0]}")

# 2. ファイルの実在確認
target_file = os.path.join(current_dir, 'core', 'ledger', 'ledger.py')
print(f"\n[Check 1] ファイルの物理確認: {target_file}")

if os.path.exists(target_file):
    print("  ✅ ファイルは存在します。")
    
    # 3. 中身のチラ見せ（クラス定義があるか）
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "class Ledger" in content:
                print("  ✅ テキスト中に 'class Ledger' の定義を発見しました。")
            else:
                print("  🚨 テキスト中に 'class Ledger' が見当たりません！ファイルの中身が空か、間違っています。")
                print("--- ファイルの先頭10行 ---")
                print('\n'.join(content.splitlines()[:10]))
                print("-------------------------")
    except Exception as e:
        print(f"  🚨 ファイルを読めませんでした: {e}")
else:
    print("  ❌ ファイルが存在しません！パスが間違っています。")

# 4. インポート実験
print(f"\n[Check 2] Pythonによるインポート実験")
try:
    # core.ledger.ledger モジュールの場所を探る
    spec = importlib.util.find_spec("core.ledger.ledger")
    if spec:
        print(f"  ✅ モジュールは見つかりました: {spec.origin}")
    else:
        print("  ❌ core.ledger.ledger モジュール自体が見つかりません。")

    # 実際にインポートしてみる
    from core.ledger.ledger import Ledger
    print("  🎉 成功！ Ledgerクラスをインポートできました。")
    print(f"  クラスの正体: {Ledger}")

except ImportError as e:
    print(f"  ❌ インポートエラー発生: {e}")
except Exception as e:
    print(f"  ❌ 予期せぬエラー: {e}")

print("=========================================")