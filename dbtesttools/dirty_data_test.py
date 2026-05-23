"""テスト用：ランダムな汚れデータをETLとフロント経由判定へ注入する。"""
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
from application.services.etl_service import (  # noqa: E402
    is_dirty_text,
    run_candidates_etl,
    run_text_etl,
    trans_clean_text,
)
from models import AiGeneration, UserChoice, db  # noqa: E402

USERNAME = "藤井修平"
PASSWORD = "123456"
COUNT = 10

fake = Faker("ja_JP")
CONTROL_CHARS = ["\x00", "\x01", "\x02", "\x07", "\x7f"]
DIRTY_SPACES = ["  ", "\n", "\t", "\r\n"]
SYMBOLS = ["!", "?", "。", "、", "…", "※", "#"]


def random_clean_text():
    return fake.sentence(nb_words=random.randint(4, 10)).rstrip("。")


def inject_dirty_chars(text):
    parts = [
        random.choice(DIRTY_SPACES),
        text[: max(1, len(text) // 2)],
        random.choice(CONTROL_CHARS),
        random.choice(DIRTY_SPACES),
        text[max(1, len(text) // 2):],
        random.choice(DIRTY_SPACES),
    ]
    return "".join(parts)


def wrap_dirty_chars(text):
    return "".join([
        random.choice(DIRTY_SPACES),
        random.choice(CONTROL_CHARS),
        text,
        random.choice(CONTROL_CHARS),
        random.choice(DIRTY_SPACES),
    ])


def random_dirty_text():
    return inject_dirty_chars(random_clean_text())


def random_symbols_only():
    return "".join(random.choice(SYMBOLS) for _ in range(random.randint(3, 8)))


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected={expected!r}, actual={actual!r}")


def login(client):
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
        return session.get("user_id")


def create_generation(user_id, raw_candidate):
    generation = AiGeneration(
        user_id=user_id,
        input_text=random_dirty_text(),
        ai_response_text=f"1. {raw_candidate}",
    )
    db.session.add(generation)
    db.session.commit()
    return generation


def random_decision(raw_candidate):
    tier = random.choice([
        DECISION_TIER_ADOPT,
        DECISION_TIER_REVISE_ADOPT,
        DECISION_TIER_REJECT,
        DECISION_TIER_NEEDS_REVIEW,
    ])

    data = {
        "action": "decide",
        "selected_text": raw_candidate,
        "decision_tier": tier,
        "edited_text": "",
        "reject_reason": "",
        "review_note": "",
    }

    if tier == DECISION_TIER_REVISE_ADOPT:
        data["edited_text"] = random_dirty_text()
    elif tier == DECISION_TIER_REJECT:
        data["reject_reason"] = random_dirty_text()
    elif tier == DECISION_TIER_NEEDS_REVIEW:
        data["review_note"] = random_dirty_text()

    return data


def run_etl_function_tests():
    for index in range(1, COUNT + 1):
        raw_text = random_dirty_text()
        clean_text = trans_clean_text(raw_text)

        assert_equal(run_text_etl(raw_text), clean_text, f"{index}: cleanable text")
        symbols_text = random_symbols_only()
        if is_dirty_text(symbols_text):
            assert_equal(run_text_etl(symbols_text), "", f"{index}: symbols only")

        duplicated = wrap_dirty_chars(clean_text)
        another_text = f"{trans_clean_text(random_dirty_text())} {index}"
        candidates = run_candidates_etl([raw_text, duplicated, random_symbols_only(), None, another_text])

        assert_equal(candidates, [clean_text, another_text], f"{index}: candidates")
        print(f"{index}: ETL関数テストOK")


def run_frontend_dirty_save_tests():
    created_generation_ids = []
    created_choice_ids = []

    with app.app_context():
        try:
            with app.test_client() as client:
                user_id = login(client)

                for index in range(1, COUNT + 1):
                    raw_candidate = random_dirty_text().strip()
                    expected_selected_text = trans_clean_text(raw_candidate)
                    generation = create_generation(user_id, raw_candidate)
                    created_generation_ids.append(generation.id)

                    with client.session_transaction() as session:
                        session["pending_generation_id"] = generation.id
                        session["pending_prompt"] = generation.input_text
                        session["pending_candidates"] = [raw_candidate]
                        session["pending_initial_count"] = 1

                    data = random_decision(raw_candidate)
                    data["generation_id"] = generation.id
                    client.post("/dashboard", data=data, follow_redirects=True)

                    choice = UserChoice.query.filter_by(
                        user_id=user_id,
                        generation_id=generation.id,
                    ).first()

                    if not choice:
                        raise AssertionError(f"{index}: 判定結果が保存されていません。")

                    created_choice_ids.append(choice.id)
                    assert_equal(choice.selected_text, expected_selected_text, f"{index}: selected_text")

                    if data["decision_tier"] == DECISION_TIER_REVISE_ADOPT:
                        assert_equal(choice.edited_text, trans_clean_text(data["edited_text"]), f"{index}: edited_text")
                    elif data["decision_tier"] == DECISION_TIER_REJECT:
                        assert_equal(
                            choice.reject_reason,
                            trans_clean_text(data["reject_reason"]),
                            f"{index}: reject_reason",
                        )
                    elif data["decision_tier"] == DECISION_TIER_NEEDS_REVIEW:
                        assert_equal(
                            choice.review_note,
                            trans_clean_text(data["review_note"]),
                            f"{index}: review_note",
                        )

                    print(f"{index}: フロント経由保存テストOK")
        finally:
            if created_choice_ids:
                UserChoice.query.filter(UserChoice.id.in_(created_choice_ids)).delete(synchronize_session=False)
            if created_generation_ids:
                AiGeneration.query.filter(AiGeneration.id.in_(created_generation_ids)).delete(synchronize_session=False)
            db.session.commit()
            print("テストデータ削除完了")


if __name__ == "__main__":
    run_etl_function_tests()
    run_frontend_dirty_save_tests()
    print("全ての汚れデータテストが完了しました。")
