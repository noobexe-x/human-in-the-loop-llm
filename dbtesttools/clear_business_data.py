"""テスト・開発用：user 表以外の業務データを一括削除する。

本番アプリ起動には含めない。手動実行専用の DB クリーンアップツール。
判定履歴・AI生成ログを消し、ユーザーアカウントだけ残す。

使い方:
    python dbtesttools/clear_business_data.py          # 件数プレビューのみ
    python dbtesttools/clear_business_data.py --yes    # 削除実行
"""
import argparse
import sys
from pathlib import Path

# プロジェクトルートを import パスへ追加し、Flask アプリコンテキストで DB 操作する。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from models import (  # noqa: E402
    AiGeneration,
    User,
    UserChoice,
    db,
)


def clear_business_data():
    """user 表以外の業務データをすべて削除する。

    外部キー依存の順序で delete する（子テーブル → 親テーブル）。
    user 表は触らない。
    """
    counts = {
        # 判定イベント（user, ai_generation への FK）
        "user_choice": UserChoice.query.delete(),
        # AI 生成ログ（user への FK）
        "ai_generation": AiGeneration.query.delete(),
    }
    db.session.commit()
    return counts


def parse_args():
    parser = argparse.ArgumentParser(
        description="user 表以外（AI生成・判定など）のテストデータを削除する。"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="確認後に実行する。指定しない場合は件数のみ表示する。",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with app.app_context():
        user_count = User.query.count()
        pending = {
            "user_choice": UserChoice.query.count(),
            "ai_generation": AiGeneration.query.count(),
        }

        print("=== 削除前 ===")
        print(f"user（保持）: {user_count} 件")
        for table, count in pending.items():
            print(f"{table}: {count} 件")

        if not args.yes:
            print("\nプレビューのみです。削除する場合は --yes を付けて実行してください。")
            return

        deleted = clear_business_data()

        print("\n=== 削除完了 ===")
        for table, count in deleted.items():
            print(f"{table}: {count} 件")
        print(f"user（保持）: {User.query.count()} 件")


if __name__ == "__main__":
    main()
