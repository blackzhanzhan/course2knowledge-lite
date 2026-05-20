from __future__ import annotations

import re
from typing import Any

_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")


def answer_course_question(
    *,
    store: Any,
    course_id: str,
    question: str,
    limit: int = 5,
) -> dict[str, Any]:
    normalized_question = str(question or "").strip()
    if not normalized_question:
        return _blocked_response(
            course_id=course_id,
            question=normalized_question,
            reason="question_required",
            message="A question is required before Course2Knowledge Lite can search transcript evidence.",
        )

    query = _question_to_query(normalized_question)
    hits = store.search_transcripts(course_id, query, limit=limit)
    if not hits:
        return _blocked_response(
            course_id=course_id,
            question=normalized_question,
            reason="no_transcript_evidence",
            message="No matching transcript evidence was found in this local course store.",
            query=query,
        )

    citations = [dict(hit["citation"]) for hit in hits]
    evidence_texts = [str(citation.get("text", "") or "").strip() for citation in citations]
    return {
        "status": "answered",
        "course_id": course_id,
        "question": normalized_question,
        "query": query,
        "answer": _compose_answer(evidence_texts, question=normalized_question),
        "citations": citations,
        "citation_count": len(citations),
        "evidence_snippets": [str(hit.get("snippet", "") or "") for hit in hits],
        "limits": {
            "mode": "transcript_citation_only",
            "external_llm_used": False,
        },
    }


def _blocked_response(
    *,
    course_id: str,
    question: str,
    reason: str,
    message: str,
    query: str = "",
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "course_id": course_id,
        "question": question,
        "query": query,
        "reason": reason,
        "answer": message,
        "citations": [],
        "citation_count": 0,
        "limits": {
            "mode": "transcript_citation_only",
            "external_llm_used": False,
        },
    }


def _question_to_query(question: str) -> str:
    ascii_terms = _ASCII_TOKEN.findall(question)
    cjk_terms = _CJK_RUN.findall(question)
    terms: list[str] = []
    for term in [*ascii_terms, *cjk_terms]:
        cleaned = term.strip()
        if cleaned and cleaned.lower() not in {item.lower() for item in terms}:
            terms.append(cleaned)
    return " ".join(terms) if terms else question.strip()


def _compose_answer(evidence_texts: list[str], *, question: str) -> str:
    if not evidence_texts:
        return "缺少课程转写证据，无法组成答案。" if _contains_cjk(question) else "No answer can be composed without transcript evidence."
    if _contains_cjk(question):
        if len(evidence_texts) == 1:
            return f"根据命中的课程转写片段：{evidence_texts[0]}"
        joined = " ".join(f"{index}. {text}" for index, text in enumerate(evidence_texts, start=1))
        return f"根据命中的课程转写片段：{joined}"
    if len(evidence_texts) == 1:
        return f"Based on the matched transcript segment: {evidence_texts[0]}"
    joined = " ".join(f"{index}. {text}" for index, text in enumerate(evidence_texts, start=1))
    return f"Based on the matched transcript segments: {joined}"


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RUN.search(text))
