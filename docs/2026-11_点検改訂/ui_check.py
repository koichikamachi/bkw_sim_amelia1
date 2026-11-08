"""画面の自動確認（Streamlit AppTest）：当座借越の入力欄・実行・上限超過の表示

実行：リポジトリの最上位で  python "docs/2026-11_点検改訂/ui_check.py"
（streamlit が必要）
"""
import os

from streamlit.testing.v1 import AppTest

# このファイルの位置から、リポジトリの ui/app.py を絶対パスで指す
APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ui", "app.py"))


def fresh():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def by_label(widgets, text):
    for w in widgets:
        if text in str(w.label):
            return w
    raise AssertionError(f"見つからない：{text}  候補={[w.label for w in widgets]}")


def run_sim(at):
    at.checkbox(key="disclaimer").check().run()
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at


# 1. 入力欄が表示される
at = fresh()
cb = at.checkbox(key="od_enabled")
lim = at.number_input(key="od_limit")
print("1. 切替:", cb.label, "初期値", cb.value, "／ 上限:", lim.label, "初期値", lim.value, "使用可", not lim.disabled)

# 2. 既定のまま実行（上限なし）→ 成功表示、エラーなし
at = run_sim(fresh())
print("2. success:", [s.value for s in at.success][:2], "／ error:", [e.value for e in at.error])

# 3. 上限を小さくして実行 → 当座借越の上限超過の表示
at = fresh()
at.number_input(key="od_limit").set_value(1.0).run()
at = run_sim(at)
print("3. error:", [e.value for e in at.error])

# 4. 切替を OFF → 上限欄が使えなくなり、実行はできる
at = fresh()
at.checkbox(key="od_enabled").uncheck().run()
print("4. 上限欄 disabled:", at.number_input(key="od_limit").disabled)
at = run_sim(at)
print("4. success:", [s.value for s in at.success][:1], "／ error:", [e.value for e in at.error])

# 5. 資金収支の行に当座借越が出ているか（表示用データ）
at = run_sim(fresh())
dfs = [d.value for d in at.dataframe]
found = [str(idx) for d in dfs for idx in getattr(d, "index", []) if "当座借越" in str(idx)]
found += [str(v) for d in dfs if hasattr(d, "columns") for c in d.columns for v in d[c].astype(str) if "当座借越" in v]
print("5. 表示に出る当座借越の行:", sorted(set(found))[:10])
