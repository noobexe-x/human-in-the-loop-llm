"""テスト・開発用：Faker でデモユーザーと判定履歴を一括投入する。

本番アプリ起動には含めない。clear_business_data.py で消した後の再シードなどに使う。

使い方:
    python dbtesttools/seed_fake_data.py --users 5 --password 123456
"""
import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from application.constants.decision_constants import (
    DECISION_TIER_ADOPT,
    DECISION_TIER_NEEDS_REVIEW,
    DECISION_TIER_REJECT,
    DECISION_TIER_REVISE_ADOPT,
    TIER_TO_STATUS,
)  # noqa: E402
from application.services.ai_service import MAX_CANDIDATES, MIN_CANDIDATES  # noqa: E402
from models import AiGeneration, User, UserChoice, db  # noqa: E402


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def unique_username(fake, index):
    """既存DBと衝突しないデモユーザー名を生成する。"""
    base_name = fake.unique.name().replace(" ", "") or f"demo_user_{index}"
    for attempt in range(100):
        suffix = "" if attempt == 0 else f"_{index}_{attempt}"
        username = f"{base_name[:80 - len(suffix)]}{suffix}"
        if not User.query.filter_by(username=username).first():
            return username
    raise RuntimeError("ユニークなデモユーザー名を生成できませんでした。")


def fake_question(fake):
    """Fakerを使ってランダムな日本語風の質問文を生成する。"""
    return fake.sentence(nb_words=random.randint(8, 16))


def fake_ai_response(fake):
    """番号付きのAI候補文と、選択保存用の候補リストを生成する。"""
    target_count = random.randint(MIN_CANDIDATES, MAX_CANDIDATES)
    options = []
    seen_options = set()
    while len(options) < target_count:
        option = fake.sentence(nb_words=random.randint(5, 12)).rstrip("。")
        if option in seen_options:
            continue
        options.append(option)
        seen_options.add(option)
    return "\n".join(f"{index}. {option}" for index, option in enumerate(options, start=1)), options


def fake_decision(fake, selected_text):
    """4段階判定のデモデータを生成する。"""
    tier = random.choices(
        [DECISION_TIER_ADOPT, DECISION_TIER_REVISE_ADOPT, DECISION_TIER_REJECT, DECISION_TIER_NEEDS_REVIEW],
        weights=[3, 4, 2, 1],
        k=1,
    )[0]
    edited_text = None
    reject_reason = None
    review_note = None

    if tier == DECISION_TIER_REVISE_ADOPT:
        edited_text = f"{selected_text}（{fake.word()}向けに修正）"
    elif tier == DECISION_TIER_REJECT:
        reject_reason = random.choice(["来源不明", "表达が抽象的", "事実確認が必要"])
    elif tier == DECISION_TIER_NEEDS_REVIEW:
        review_note = random.choice(["後で確認", "出典待ち", "表現を再検討"])

    return tier, TIER_TO_STATUS[tier], edited_text, reject_reason, review_note


def seed_fake_data(user_count, generations_per_user, choices_per_generation, password, locale):
    fake = Faker(locale)
    created_users = 0
    created_generations = 0
    created_choices = 0

    with app.app_context():
        for user_index in range(1, user_count + 1):
            user = User(
                username=unique_username(fake, user_index),
                is_admin=False,
                can_access=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            created_users += 1

            for _ in range(generations_per_user):
                question = fake_question(fake)
                ai_response_text, candidates = fake_ai_response(fake)
                generation = AiGeneration(
                    user_id=user.id,
                    input_text=question,
                    ai_response_text=ai_response_text,
                    created_at=utc_now() - timedelta(days=random.randint(0, 30)),
                )
                db.session.add(generation)
                db.session.flush()
                created_generations += 1

                selected_candidates = random.sample(
                    candidates,
                    k=min(choices_per_generation, len(candidates)),
                )
                for selected_text in selected_candidates:
                    tier, status, edited_text, reject_reason, review_note = fake_decision(
                        fake, selected_text
                    )
                    choice = UserChoice(
                        user_id=user.id,
                        generation_id=generation.id,
                        question_text=question,
                        selected_text=selected_text,
                        edited_text=edited_text,
                        reject_reason=reject_reason,
                        review_note=review_note,
                        decision_tier=tier,
                        status=status,
                        created_at=generation.created_at + timedelta(minutes=random.randint(1, 20)),
                    )
                    db.session.add(choice)
                    created_choices += 1

        db.session.commit()

    print(
        "Seed complete: "
        f"{created_users} users, "
        f"{created_generations} AI generations, "
        f"{created_choices} decisions."
    )


def parse_args():
    parser = argparse.ArgumentParser(description="デモ用ユーザーと判定履歴を投入する。")
    parser.add_argument("--users", type=int, default=5, help="作成するデモユーザー数。")
    parser.add_argument(
        "--generations-per-user",
        type=int,
        default=3,
        help="ユーザーごとに作成するAI生成履歴数。",
    )
    parser.add_argument(
        "--choices-per-generation",
        type=int,
        default=1,
        help="AI生成履歴ごとに作成する判定履歴数。",
    )
    parser.add_argument("--password", default="123456", help="生成ユーザーに設定するパスワード。")
    parser.add_argument("--locale", default="ja_JP", help="Fakerのロケール。例: zh_CN, ja_JP。")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    seed_fake_data(
        user_count=args.users,
        generations_per_user=args.generations_per_user,
        choices_per_generation=args.choices_per_generation,
        password=args.password,
        locale=args.locale,
    )
