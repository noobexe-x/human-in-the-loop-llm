from application.constants.decision_constants import (
    DECISION_TIER_REJECT,
    DECISION_TIER_REVISE_ADOPT,
    TIER_TO_STATUS,
)
from application.services.etl_service import trans_clean_text
from models import UserChoice


def validate_decision_form(decision_tier, selected_text, edited_text, reject_reason, review_note):
    """4段階判定フォームの入力を検証する。"""
    selected_text = trans_clean_text(selected_text)
    edited_text = trans_clean_text(edited_text)
    reject_reason = trans_clean_text(reject_reason)
    review_note = trans_clean_text(review_note)

    if decision_tier not in TIER_TO_STATUS:
        return False, "判定を選択してください。", None

    if not selected_text:
        return False, "候補を1つ選択してください。", None

    if decision_tier == DECISION_TIER_REVISE_ADOPT and not edited_text:
        return False, "修正して採用の場合は、修正後テキストを入力してください。", None

    if decision_tier == DECISION_TIER_REJECT and not reject_reason:
        return False, "不採用の場合は、不採用理由を入力してください。", None

    return True, None, {
        "selected_text": selected_text,
        "edited_text": edited_text or None,
        "reject_reason": reject_reason or None,
        "review_note": review_note or None,
    }


def build_user_choice(user_id, generation, decision_tier, cleaned_fields):
    """判定結果から UserChoice レコードを組み立てる。"""
    return UserChoice(
        user_id=user_id,
        generation_id=generation.id,
        question_text=generation.input_text,
        selected_text=cleaned_fields["selected_text"],
        edited_text=cleaned_fields["edited_text"],
        reject_reason=cleaned_fields["reject_reason"],
        review_note=cleaned_fields["review_note"],
        decision_tier=decision_tier,
        status=TIER_TO_STATUS[decision_tier],
    )
