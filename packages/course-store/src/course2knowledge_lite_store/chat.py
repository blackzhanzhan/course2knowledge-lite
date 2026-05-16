from __future__ import annotations

import re
from typing import Any


_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")

_VISUAL_TERMS = {
    "diagram",
    "image",
    "picture",
    "screenshot",
    "visual",
    "\u56fe",
    "\u56fe\u50cf",
    "\u56fe\u7247",
    "\u56fe\u793a",
    "\u622a\u56fe",
    "\u89c6\u89c9",
    "\u6d41\u7a0b\u56fe",
}
_GUIDE_TERMS = {
    "continue",
    "guide",
    "recap",
    "self-check",
    "self_check",
    "walkthrough",
    "\u5bfc\u8bfb",
    "\u7ee7\u7eed",
    "\u590d\u76d8",
    "\u81ea\u6d4b",
}
_CARD_TERMS = {"card", "cards", "knowledge", "\u5361\u7247", "\u77e5\u8bc6\u5361"}
_STATE_TERMS = {"bookmark", "bookmarks", "note", "notes", "progress", "\u4e66\u7b7e", "\u7b14\u8bb0", "\u8fdb\u5ea6"}


class LiteChatCore:
    """Deterministic chat orchestration over the public Course2Knowledge Lite store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def run_turn(
        self,
        *,
        course_id: str,
        message: str,
        thread_id: str = "",
        channel: str = "web",
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_course_id = str(course_id or "").strip()
        cleaned_message = str(message or "").strip()
        if not cleaned_course_id:
            raise ValueError("course_id is required")
        if not cleaned_message:
            raise ValueError("message is required")

        course = self.store.read_course(cleaned_course_id)
        thread = self._thread_for_turn(
            course_id=cleaned_course_id,
            message=cleaned_message,
            thread_id=thread_id,
            channel=channel,
            now=now,
        )
        message_count = len(self.store.list_chat_messages(str(thread["thread_id"])))
        user_message = self.store.append_chat_message(
            str(thread["thread_id"]),
            "user",
            cleaned_message,
            message_id=f"{thread['thread_id']}::msg_{message_count + 1:05d}_user",
            now=now,
        )

        route = _route(cleaned_message)
        event_specs, assistant_text, status = self._build_response(
            course=course,
            course_id=cleaned_course_id,
            message=cleaned_message,
            route=route,
        )
        assistant_message = self.store.append_chat_message(
            str(thread["thread_id"]),
            "assistant",
            assistant_text,
            message_id=f"{thread['thread_id']}::msg_{message_count + 2:05d}_assistant",
            now=now,
        )
        events = self._persist_events(
            thread_id=str(thread["thread_id"]),
            message_id=str(assistant_message["message_id"]),
            specs=event_specs,
            now=now,
        )

        return {
            "status": status,
            "route": route,
            "thread": self.store.read_chat_thread(str(thread["thread_id"])),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "events": events,
        }

    def _thread_for_turn(
        self,
        *,
        course_id: str,
        message: str,
        thread_id: str,
        channel: str,
        now: str,
    ) -> dict[str, Any]:
        cleaned_thread_id = str(thread_id or "").strip()
        if cleaned_thread_id:
            thread = self.store.read_chat_thread(cleaned_thread_id)
            if str(thread.get("course_id") or "") != course_id:
                raise ValueError(f"chat thread does not belong to course: {cleaned_thread_id}")
            return thread
        return self.store.create_chat_thread(
            course_id,
            title=_thread_title(message),
            channel=channel,
            now=now,
        )

    def _build_response(
        self,
        *,
        course: dict[str, Any],
        course_id: str,
        message: str,
        route: str,
    ) -> tuple[list[dict[str, Any]], str, str]:
        if route == "visual_evidence":
            return self._visual_response(course_id=course_id, message=message)
        if route == "guide":
            return self._guide_response(course_id=course_id)
        if route == "cards":
            return self._cards_response(course_id=course_id)
        if route == "notes_progress":
            return self._notes_progress_response(course_id=course_id)
        return self._search_response(course=course, course_id=course_id, message=message)

    def _search_response(
        self,
        *,
        course: dict[str, Any],
        course_id: str,
        message: str,
    ) -> tuple[list[dict[str, Any]], str, str]:
        query = _question_to_query(message)
        specs = [_event("tool_start", "transcript_search", {"course_id": course_id, "query": query, "limit": 5})]
        hits = self.store.search_transcripts(course_id, query, limit=5)
        specs.append(
            _event(
                "tool_result",
                "transcript_search",
                {
                    "course_id": course_id,
                    "query": query,
                    "hit_count": len(hits),
                    "hits": hits,
                },
            )
        )
        if not hits:
            text = "No matching transcript evidence was found in this local course store."
            specs.append(_event("error", "", {"reason": "no_transcript_evidence", "message": text}))
            specs.append(_event("done", "", {"status": "blocked"}))
            return specs, text, "blocked"
        citations = [dict(hit["citation"]) for hit in hits]
        answer = _compose_answer([str(item.get("text") or "") for item in citations], course=course)
        specs.append(
            _event(
                "message_delta",
                "",
                {
                    "delta": answer,
                    "citations": citations,
                    "citation_count": len(citations),
                },
            )
        )
        specs.append(_event("done", "", {"status": "completed"}))
        return specs, answer, "completed"

    def _visual_response(self, *, course_id: str, message: str) -> tuple[list[dict[str, Any]], str, str]:
        specs = [_event("tool_start", "visual_evidence_select", {"course_id": course_id, "query": message})]
        try:
            visual = self.store.select_visual_evidence(course_id=course_id, query=message)
        except ValueError as exc:
            text = str(exc)
            specs.append(
                _event(
                    "tool_result",
                    "visual_evidence_select",
                    {"course_id": course_id, "matched": False, "visual_evidence": {}},
                )
            )
            specs.append(_event("error", "", {"reason": "no_visual_evidence", "message": text}))
            specs.append(_event("done", "", {"status": "blocked"}))
            return specs, text, "blocked"

        specs.append(
            _event(
                "tool_result",
                "visual_evidence_select",
                {"course_id": course_id, "matched": True, "visual_evidence": visual},
            )
        )
        specs.append(
            _event(
                "media",
                "visual_evidence_select",
                {
                    "media_type": "image",
                    "source": "VISUAL_EVIDENCE",
                    "visual_id": str(visual.get("visual_id") or ""),
                    "image_path": str(visual.get("image_path") or ""),
                    "title": str(visual.get("title") or ""),
                    "explanation": str(visual.get("explanation") or ""),
                },
            )
        )
        text = _visual_answer(visual)
        specs.append(_event("message_delta", "", {"delta": text, "visual_id": str(visual.get("visual_id") or "")}))
        specs.append(_event("done", "", {"status": "completed"}))
        return specs, text, "completed"

    def _guide_response(self, *, course_id: str) -> tuple[list[dict[str, Any]], str, str]:
        specs = [_event("tool_start", "lite_learning_guide", {"course_id": course_id})]
        lectures = self.store.read_lectures(course_id)
        progress_items = self.store.list_reading_progress(course_id=course_id)
        progress_by_lecture_id = {str(item.get("lecture_id") or ""): dict(item) for item in progress_items}
        selected = _next_public_lecture(self.store, course_id, lectures, progress_by_lecture_id)
        payload = {
            "course_id": course_id,
            "lecture_count": len(lectures),
            "reading_progress": progress_items,
            "next_lecture": selected,
            "read_only": True,
        }
        specs.append(_event("tool_result", "lite_learning_guide", payload))
        if not selected:
            text = "No lectures are available in this local course store."
            specs.append(_event("error", "", {"reason": "no_lectures", "message": text}))
            specs.append(_event("done", "", {"status": "blocked"}))
            return specs, text, "blocked"
        text = f"Continue with lecture {selected['sequence']}: {selected['title']}."
        specs.append(_event("message_delta", "", {"delta": text, "lecture": selected}))
        specs.append(_event("done", "", {"status": "completed"}))
        return specs, text, "completed"

    def _cards_response(self, *, course_id: str) -> tuple[list[dict[str, Any]], str, str]:
        specs = [_event("tool_start", "knowledge_cards_list", {"course_id": course_id})]
        cards = self.store.list_knowledge_cards(course_id=course_id)
        if not cards:
            generated = self.store.generate_knowledge_cards(course_id)
            cards = list(generated.get("cards") or [])
        payload = {"course_id": course_id, "card_count": len(cards), "cards": cards[:5]}
        specs.append(_event("tool_result", "knowledge_cards_list", payload))
        if not cards:
            text = "No knowledge cards could be built from local transcript evidence."
            specs.append(_event("error", "", {"reason": "no_card_evidence", "message": text}))
            specs.append(_event("done", "", {"status": "blocked"}))
            return specs, text, "blocked"
        titles = ", ".join(str(card.get("title") or card.get("card_id") or "") for card in cards[:3])
        text = f"Found {len(cards)} local knowledge cards. First cards: {titles}."
        specs.append(_event("message_delta", "", {"delta": text, "card_count": len(cards), "cards": cards[:3]}))
        specs.append(_event("done", "", {"status": "completed"}))
        return specs, text, "completed"

    def _notes_progress_response(self, *, course_id: str) -> tuple[list[dict[str, Any]], str, str]:
        specs = [_event("tool_start", "notes_progress_read", {"course_id": course_id})]
        notes = self.store.list_notes(course_id=course_id)
        progress_items = self.store.list_reading_progress(course_id=course_id)
        bookmarks = self.store.list_bookmarks(course_id=course_id)
        payload = {
            "course_id": course_id,
            "note_count": len(notes),
            "bookmark_count": len(bookmarks),
            "reading_progress": progress_items,
            "notes": notes[:5],
            "bookmarks": bookmarks[:5],
        }
        specs.append(_event("tool_result", "notes_progress_read", payload))
        read_count = sum(1 for item in progress_items if str(item.get("status") or "") == "read")
        text = f"Local notes: {len(notes)}. Bookmarks: {len(bookmarks)}. Read lectures: {read_count}."
        specs.append(_event("message_delta", "", {"delta": text, **payload}))
        specs.append(_event("done", "", {"status": "completed"}))
        return specs, text, "completed"

    def _persist_events(
        self,
        *,
        thread_id: str,
        message_id: str,
        specs: list[dict[str, Any]],
        now: str,
    ) -> list[dict[str, Any]]:
        events = []
        for index, spec in enumerate(specs, start=1):
            events.append(
                self.store.append_chat_event(
                    thread_id,
                    str(spec["event_type"]),
                    dict(spec["payload"]),
                    message_id=message_id,
                    tool_name=str(spec.get("tool_name") or ""),
                    event_id=f"{message_id}::evt_{index:03d}",
                    now=now,
                )
            )
        return events


def _event(event_type: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event_type": event_type, "tool_name": tool_name, "payload": payload}


def _route(message: str) -> str:
    lowered = str(message or "").lower()
    terms = set(_terms(message))
    if terms & _VISUAL_TERMS or any(term in lowered for term in _VISUAL_TERMS if len(term) == 1):
        return "visual_evidence"
    if terms & _GUIDE_TERMS:
        return "guide"
    if terms & _CARD_TERMS:
        return "cards"
    if terms & _STATE_TERMS:
        return "notes_progress"
    return "search"


def _terms(message: str) -> list[str]:
    ascii_terms = [item.lower() for item in _ASCII_TOKEN.findall(message)]
    cjk_terms = _CJK_RUN.findall(message)
    return [*ascii_terms, *cjk_terms]


def _question_to_query(question: str) -> str:
    terms: list[str] = []
    for term in _terms(question):
        if term and term.lower() not in {item.lower() for item in terms}:
            terms.append(term)
    return " ".join(terms) if terms else question.strip()


def _compose_answer(evidence_texts: list[str], *, course: dict[str, Any]) -> str:
    title = str(course.get("title") or "this course").strip()
    cleaned = [text.strip() for text in evidence_texts if text.strip()]
    if len(cleaned) == 1:
        return f"Based on local transcript evidence in {title}: {cleaned[0]}"
    joined = " ".join(f"{index}. {text}" for index, text in enumerate(cleaned, start=1))
    return f"Based on local transcript evidence in {title}: {joined}"


def _visual_answer(visual: dict[str, Any]) -> str:
    title = str(visual.get("title") or visual.get("visual_id") or "Selected visual evidence")
    explanation = str(visual.get("explanation") or "").strip()
    if explanation:
        return f"{title}: {explanation}"
    return title


def _thread_title(message: str) -> str:
    collapsed = " ".join(str(message or "").split())
    if len(collapsed) <= 48:
        return collapsed or "New chat"
    return f"{collapsed[:45].rstrip()}..."


def _next_public_lecture(
    store: Any,
    course_id: str,
    lectures: list[dict[str, Any]],
    progress_by_lecture_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sorted_lectures = sorted(
        [dict(item) for item in lectures],
        key=lambda item: (int(item.get("sequence") or 0), str(item.get("lecture_id") or "")),
    )
    for lecture in sorted_lectures:
        lecture_id = str(lecture.get("lecture_id") or "")
        status = str((progress_by_lecture_id.get(lecture_id) or {}).get("status") or lecture.get("read_status") or "not_started")
        if status != "read" and store.read_transcript_segments_if_exists(course_id, lecture_id):
            return _lecture_public(lecture)
    return _lecture_public(sorted_lectures[0]) if sorted_lectures else {}


def _lecture_public(lecture: dict[str, Any]) -> dict[str, Any]:
    return {
        "lecture_id": str(lecture.get("lecture_id") or ""),
        "course_id": str(lecture.get("course_id") or ""),
        "title": str(lecture.get("title") or lecture.get("lecture_id") or "Untitled lecture"),
        "sequence": int(lecture.get("sequence") or 0),
        "source_url": str(lecture.get("source_url") or ""),
        "source_id": str(lecture.get("source_id") or ""),
        "read_status": str(lecture.get("read_status") or "not_started"),
    }
