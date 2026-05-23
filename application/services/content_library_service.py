from application.constants.decision_constants import STATUS_PENDING, STATUS_PUBLISHED, STATUS_REJECTED
from models import UserChoice

PUBLISHED_PROMPT_LIMIT = 5
REJECT_PROMPT_LIMIT = 3


def get_published_choices(user_id, limit=PUBLISHED_PROMPT_LIMIT):
    """status=published の正例だけを取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id, status=STATUS_PUBLISHED)
        .order_by(UserChoice.created_at.desc())
        .limit(limit)
        .all()
    )


def get_rejected_choices(user_id, limit=REJECT_PROMPT_LIMIT):
    """status=rejected の不採用理由を取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id, status=STATUS_REJECTED)
        .filter(UserChoice.reject_reason.isnot(None))
        .filter(UserChoice.reject_reason != "")
        .order_by(UserChoice.created_at.desc())
        .limit(limit)
        .all()
    )


def get_pending_choices(user_id):
    """status=pending の要確認キューを取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id, status=STATUS_PENDING)
        .order_by(UserChoice.created_at.desc())
        .all()
    )


def build_content_library_prompt_context(user_id):
    """採用済みコンテンツと不採用理由をPromptへ差し込む。"""
    if not user_id:
        return ""

    published = get_published_choices(user_id)
    rejected = get_rejected_choices(user_id)
    if not published and not rejected:
        return ""

    sections = []
    if published:
        examples = []
        for choice in published:
            text = choice.canonical_text()
            if not text:
                continue
            examples.append(f"- {text}")
        if examples:
            sections.append(
                "採用済みコンテンツ例:\n"
                + "\n".join(examples)
                + "\n引用しやすい構造・粒度を参考に、複数の異なる候補を出してください。"
            )

    if rejected:
        reasons = [f"- {choice.reject_reason.strip()}" for choice in rejected if choice.reject_reason.strip()]
        if reasons:
            sections.append(
                "過去の不採用理由（避けること）:\n"
                + "\n".join(reasons)
            )

    if not sections:
        return ""

    return "\n\n".join(sections) + "\n\n"
