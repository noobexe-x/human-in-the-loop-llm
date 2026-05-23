import re


CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_PATTERN = re.compile(r"\s+")
MIN_TEXT_LENGTH = 2


def extract_text(value):
    """ETL extract：生の入力を受け取り、文字列へ正規化する。"""
    if value is None:
        return ""
    return str(value)


def trans_clean_text(value):
    """ETL trans：明らかな汚れ文字を除去し、空白を圧縮する。"""
    text = extract_text(value)
    text = CONTROL_CHAR_PATTERN.sub("", text)
    return SPACE_PATTERN.sub(" ", text).strip()


def is_dirty_text(value):
    """デモ用ETLとして、汚れデータ判定ルールは最小限に保つ。"""
    text = trans_clean_text(value)
    if len(text) < MIN_TEXT_LENGTH:
        return True
    if not re.search(r"[\w\u3040-\u30ff\u3400-\u9fff]", text):
        return True
    return False


def run_text_etl(value):
    """小さなテキストETLを実行し、清潔な文字列または空文字を返す。"""
    text = trans_clean_text(value)
    if is_dirty_text(text):
        return ""
    return text


def run_candidates_etl(candidates, limit=None):
    """候補文字列を清洗し、汚れ行の除外、重複排除、件数制限を行う。"""
    cleaned_candidates = []
    seen = set()
    for candidate in candidates:
        text = run_text_etl(candidate)
        if not text or text in seen:
            continue
        cleaned_candidates.append(text)
        seen.add(text)
        if limit and len(cleaned_candidates) >= limit:
            break
    return cleaned_candidates
