import logging
import re

from flask import current_app
from openai import OpenAI

from application.services.content_library_service import build_content_library_prompt_context
from application.services.etl_service import run_candidates_etl, run_text_etl


MIN_CANDIDATES = 5
MAX_CANDIDATES = 10


def get_client():
    """現在のFlask設定からDeepSeek/OpenAI互換クライアントを作成する。"""
    return OpenAI(
        api_key=current_app.config['DEEPSEEK_API_KEY'],
        base_url=current_app.config['DEEPSEEK_BASE_URL']
    )


def get_ai_response(message, max_tokens):
    """AI APIへリクエストを送り、返答の生テキストを返す。"""
    try:
        logging.info(f"DeepSeek リクエスト: {message} (max_tokens={max_tokens})")
        response = get_client().chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": message}
            ],
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content.strip()
        logging.info(f"DeepSeek 応答: {result}")
        return result
    except Exception as e:
        logging.error(f"DeepSeek エラー: {str(e)}", exc_info=True)
        return f"[AI エラー: {str(e)}]"


def apply_prompt_filter(message):
    """AI APIへ送る前に、候補抽出ルールを追加する。"""
    return (
        "次のユーザー入力から、他のAIが引用しやすい候補情報を複数抽出してください。\n"
        "候補は定義が明確で、単独でも意味が通る短文にしてください。\n"
        "タイトル、キーワード、名称、要点、FAQ項目など、入力内容に合うものを選んでください。\n"
        f"候補は必ず{MIN_CANDIDATES}個以上、最大{MAX_CANDIDATES}個出してください。\n"
        "入力文をそのまま1個だけ返すのではなく、内容を分解・具体化・言い換えした異なる候補を出してください。\n"
        "説明文は不要です。\n"
        "出力形式は「1. 候補」のように、1行に1候補だけを書いてください。\n\n"
        f"ユーザー入力: {message}"
    )


def build_personalized_prompt(message, user_id=None):
    """採用済みコンテンツと不採用理由をPromptへ差し込む。"""
    clean_message = run_text_etl(message)
    return build_content_library_prompt_context(user_id) + apply_prompt_filter(clean_message)


def parse_candidates(text):
    """AIの番号付き複数行テキストを候補リストへ分解する。"""
    candidates = []
    for line in text.splitlines():
        item = line.strip()
        if not item:
            continue
        item = item.lstrip("-* ")
        item = re.sub(r"^\d+[\.\)、\s]+", "", item).strip()
        if item:
            candidates.append(item)
    return run_candidates_etl(candidates, limit=MAX_CANDIDATES)


def get_ai_candidates(message, user_id=None):
    """ユーザー入力から候補を生成し、AIの生テキストと候補リストを返す。"""
    prompt = build_personalized_prompt(message, user_id=user_id)
    result = get_ai_response(prompt, current_app.config['DEMO_MAX_TOKENS'])
    candidates = parse_candidates(result)
    if len(candidates) < MIN_CANDIDATES:
        retry_prompt = (
            f"{prompt}\n\n"
            f"前回は候補が{len(candidates)}個しかありませんでした。"
            f"必ず{MIN_CANDIDATES}個以上、互いに異なる候補を番号付きで出し直してください。"
        )
        result = get_ai_response(retry_prompt, current_app.config['DEMO_MAX_TOKENS'])
        candidates = parse_candidates(result)
    return result, candidates
