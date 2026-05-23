# Flask AIチャットダッシュボード

ToB向け LLMO 概念デモです。管理者がユーザーを作成して利用権限を付与し、許可された一般ユーザーが AI 候補を生成します。生成された候補は **4段階判定**（採用 / 修正して採用 / 不採用 / 要確認）で整理し、採用済みコンテンツと不採用理由を次回生成時の Prompt に反映します。

## ワークフロー

```text
入力 → AI候補 → 4段階判定 → コンテンツライブラリ（published / rejected / pending）→ 次回 Prompt
```

- **採用 / 修正して採用** → `status=published` → 正例として Prompt へ反映
- **不採用** → `status=rejected` → 不採用理由を Prompt 調整へ利用
- **要確認** → `status=pending` → 次回 Prompt には反映しない

## 初期管理者

- ユーザー名: `admin`
- パスワード: `123456`

一般ユーザーは管理画面または `dbtesttools/seed_fake_data.py` で作成します。

## 起動

1. `.env.example` を複製して `.env` を作成し、APIキーなどを設定する
2. Docker またはローカル環境で起動する

Docker を使う場合:

```bash
docker compose up --build
```

ローカルで起動する場合:

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

起動後は `http://127.0.0.1:5000` にアクセスします。DBは `instance/chat.db` に保存されます。

## テストデータ（dbtesttools/）

`dbtesttools/` は本番アプリの起動には含めない、開発・デモ用の手動テストツールです。

```bash
# user 表以外の業務データを削除（プレビュー）
python dbtesttools/clear_business_data.py

# 削除実行
python dbtesttools/clear_business_data.py --yes

# デモユーザーと判定履歴を直接投入
python dbtesttools/seed_fake_data.py --users 5 --password 123456

# フロント経由でログイン、AI質問、4段階判定を実行
python dbtesttools/frontend_flow_test.py
```

## プロジェクト構成

| ファイル / ディレクトリ | 責務 |
|---|---|
| `app.py` | アプリ作成、DB初期化、ルート登録 |
| `config.py` | 環境変数とアプリ設定 |
| `models.py` | DBモデル |
| `routes.py` | Controller登録の入口 |
| `application/controllers/` | 認証、管理画面、ダッシュボードのController |
| `application/services/` | AI呼び出し、判定保存、管理画面向けDB操作などの業務ロジック |
| `application/constants/` | 4段階判定と `status` の定義 |
| `templates/` | HTML |
| `static/style.css` | スタイル |
| `dbtesttools/` | 手動テスト用ツール（削除・シード・フロント経由テスト） |

## 注意

- `.env`、`instance/chat.db`、`venv/` はコミットしない
- 本番では初期管理者パスワードを変更する
- スキーマ変更後は既存 `instance/chat.db` を削除するか、起動時 migration に任せる

