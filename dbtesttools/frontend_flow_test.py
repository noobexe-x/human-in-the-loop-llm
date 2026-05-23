"""テスト用：フロント経由でAI質問と4段階判定を10回実行する。"""
import random
import sys
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from application.constants.decision_constants import (  # noqa: E402
    DECISION_TIER_ADOPT,
    DECISION_TIER_NEEDS_REVIEW,
    DECISION_TIER_REJECT,
    DECISION_TIER_REVISE_ADOPT,
)

USERNAME = "藤井修平"
PASSWORD = "123456"
COUNT = 10

fake = Faker("ja_JP")


def random_question():
    return fake.sentence(nb_words=random.randint(8, 16))


def random_decision(selected_text):
    tier = random.choice([
        DECISION_TIER_ADOPT,
        DECISION_TIER_REVISE_ADOPT,
        DECISION_TIER_REJECT,
        DECISION_TIER_NEEDS_REVIEW,
    ])

    data = {
        "action": "decide",
        "selected_text": selected_text,
        "decision_tier": tier,
        "edited_text": "",
        "reject_reason": "",
        "review_note": "",
    }

    if tier == DECISION_TIER_REVISE_ADOPT:
        data["edited_text"] = f"{selected_text}（{fake.sentence(nb_words=6)}）"
    elif tier == DECISION_TIER_REJECT:
        data["reject_reason"] = fake.sentence(nb_words=random.randint(8, 16))
    elif tier == DECISION_TIER_NEEDS_REVIEW:
        data["review_note"] = fake.sentence(nb_words=random.randint(8, 16))

    return data


with app.test_client() as client:
    login_response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )

    if login_response.status_code not in (302, 303):
        raise RuntimeError("ログイン失敗。ユーザー名、パスワード、利用権限を確認してください。")

    with client.session_transaction() as session:
        if not session.get("user_id") or session.get("is_admin"):
            raise RuntimeError("一般ユーザーとしてログインできませんでした。")

    for index in range(1, COUNT + 1):
        client.post(
            "/dashboard",
            data={
                "action": "chat",
                "message": random_question(),
            },
            follow_redirects=True,
        )

        with client.session_transaction() as session:
            candidates = session.get("pending_candidates", [])
            generation_id = session.get("pending_generation_id")

        if not candidates:
            print(f"{index}: 候補なし")
            continue

        data = random_decision(random.choice(candidates))
        data["generation_id"] = generation_id

        client.post("/dashboard", data=data, follow_redirects=True)
        print(f"{index}: 保存完了")
