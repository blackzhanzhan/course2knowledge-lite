from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable

from .dossier_core.adapters import format_timestamp_anchor
from .dossier_core.markdown import build_markdown_render_context, render_lecture_markdown
from .dossier_core.pipeline import compile_lite_lecture_dossier_from_segments
from .dossier_core.pipeline_tutoring import enrich_tutoring_fields


_SPACE_PATTERN = re.compile(r"\s+")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_DISCOURSE_PREFIX_PATTERN = re.compile(
    r"^(那么|然后|所以|这里|其实|也就是说|接下来|下面|刚才|大家|我们|好|好的|okay|ok)\s*",
    flags=re.IGNORECASE,
)
_LOW_INFORMATION_PATTERNS = (
    re.compile(r"^(好|好的|嗯|啊|那么|然后|所以|接下来|下面)$", flags=re.IGNORECASE),
    re.compile(r"^(我们)?(正式)?开始(进入)?"),
    re.compile(r"^(本小节|这一讲|这个视频).{0,12}(结束|开始|主要讲)?$"),
    re.compile(r"第[一二三四五六七八九十\d]+个视频当中"),
    re.compile(r"视频当中$"),
    re.compile(r"^(谢谢|下节课再见|我们下集再见)$"),
)
_COURSE_LOGISTICS_TERMS = (
    "主讲人",
    "学长",
    "学姐",
    "京东",
    "天猫",
    "当当",
    "QQ群",
    "群号",
    "免费资料",
    "交流",
    "购买",
)
_TEACHABLE_LOGISTICS_ALLOW_TERMS = (
    "练习",
    "习题",
    "笔记",
    "自测",
    "掌握",
    "学习效果",
    "课程目标",
)
_CORE_TAG_TERMS = (
    "RAG",
    "Agent",
    "MCP",
    "embedding",
    "向量",
    "检索",
    "召回",
    "重排",
    "证据",
    "引用",
    "上下文",
    "语义",
    "知识库",
    "视频",
    "Markdown",
    "ER",
    "数据",
    "结构",
    "算法",
    "复杂度",
    "关系",
    "规则",
    "方法",
    "边界",
    "前提",
    "步骤",
    "例子",
    "问题",
    "答案",
)
_ENGLISH_STOP_TAGS = {
    "and",
    "after",
    "an",
    "answer",
    "answering",
    "answers",
    "before",
    "by",
    "course",
    "evidence",
    "final",
    "focuses",
    "grounded",
    "in",
    "is",
    "it",
    "lecture",
    "needs",
    "on",
    "one",
    "step",
    "supported",
    "that",
    "the",
    "then",
    "this",
    "three",
    "two",
    "whether",
}
_ENGLISH_TECH_TRANSLATIONS = (
    (re.compile(r"\bRAG accuracy optimization\b", re.IGNORECASE), "RAG 准确率优化"),
    (re.compile(r"\bRAG retrieves course evidence\b", re.IGNORECASE), "RAG 召回课程证据"),
    (re.compile(r"\bchecking retrieval recall\b", re.IGNORECASE), "检查检索召回"),
    (re.compile(r"\bimproving chunking and reranking\b", re.IGNORECASE), "改进切片与重排"),
    (
        re.compile(r"\bverifying whether the final answer is supported by cited course evidence\b", re.IGNORECASE),
        "核验最终答案是否由课程证据支撑",
    ),
    (re.compile(r"\bRAG retrieves evidence\b", re.IGNORECASE), "RAG 召回证据"),
    (re.compile(r"\bAgent calls tools\b", re.IGNORECASE), "Agent 调用工具"),
    (re.compile(r"\bAgent plans tool calls\b", re.IGNORECASE), "Agent 规划工具调用"),
    (re.compile(r"\bknowledge base\b", re.IGNORECASE), "知识库"),
    (re.compile(r"\bsemantic unit\b", re.IGNORECASE), "语义单元"),
    (re.compile(r"\bThis lecture focuses on\b", re.IGNORECASE), "本讲聚焦"),
    (re.compile(r"\bStep one is\b", re.IGNORECASE), "第一步是"),
    (re.compile(r"\bStep two is\b", re.IGNORECASE), "第二步是"),
    (re.compile(r"\bStep three is\b", re.IGNORECASE), "第三步是"),
)


@dataclass(frozen=True)
class LiteLectureDossier:
    course_title: str
    lecture_id: str
    lecture_title: str
    source_url: str
    lecture_summary: str
    sections: list[dict[str, Any]]
    anchors: list[dict[str, Any]]
    atoms: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    review_questions: list[str]
    prerequisites: list[dict[str, Any]]
    pitfalls: list[dict[str, Any]]
    minimal_checks: list[dict[str, Any]]
    minimal_examples: list[dict[str, Any]]
    followup_scaffold: list[dict[str, Any]]
    feedback_routes: list[dict[str, Any]]
    search_hooks: list[dict[str, Any]]
    provider: str = "course2knowledge_lite_child_adapter"
    compile_source: str = "deterministic_fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "lite_lecture_dossier.mother_shape.v1",
            "course_title": self.course_title,
            "course_name": self.course_title,
            "lecture_id": self.lecture_id,
            "lecture_title": self.lecture_title,
            "source_url": self.source_url,
            "provider": self.provider,
            "compile_source": self.compile_source,
            "subtitle_source_kind": "transcript_segments",
            "lecture_summary": self.lecture_summary,
            "sections": [dict(item) for item in self.sections],
            "anchors": [dict(item) for item in self.anchors],
            "atoms": [dict(item) for item in self.atoms],
            "relations": [dict(item) for item in self.relations],
            "review_questions": list(self.review_questions),
            "prerequisites": [dict(item) for item in self.prerequisites],
            "pitfalls": [dict(item) for item in self.pitfalls],
            "minimal_checks": [dict(item) for item in self.minimal_checks],
            "minimal_examples": [dict(item) for item in self.minimal_examples],
            "followup_scaffold": [dict(item) for item in self.followup_scaffold],
            "feedback_routes": [dict(item) for item in self.feedback_routes],
            "search_hooks": [dict(item) for item in self.search_hooks],
        }


def build_lite_lecture_dossier(
    *,
    course: dict[str, Any] | None = None,
    lecture: dict[str, Any] | None = None,
    segments: Iterable[dict[str, Any]] = (),
    course_title: str = "",
    lecture_title: str = "",
    lecture_id: str = "",
    source_url: str = "",
    compile_mode: str = "model",
    compile_provider: str | None = "deepseek",
    api_key: str | None = None,
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    fast_map_mode: bool = True,
    split_map_mode: bool = True,
    fast_reduce_mode: bool = True,
    lite_map_mode: bool = False,
) -> LiteLectureDossier:
    resolved_course_title = str((course or {}).get("title") or course_title or "").strip()
    resolved_lecture_title = str((lecture or {}).get("title") or lecture_title or lecture_id or "未命名课时").strip()
    resolved_lecture_id = str((lecture or {}).get("lecture_id") or lecture_id or "").strip()
    resolved_source_url = str((lecture or {}).get("source_url") or source_url or "").strip()
    normalized_segments = _normalize_segments(segments)
    normalized_compile_mode = str(compile_mode or "model").strip()
    if normalized_compile_mode not in {"fallback", "model", "auto"}:
        raise ValueError("compile_mode must be fallback, model, or auto")
    if normalized_compile_mode in {"model", "auto"}:
        try:
            compiled = compile_lite_lecture_dossier_from_segments(
                course_name=resolved_course_title,
                lecture_id=resolved_lecture_id,
                lecture_title=resolved_lecture_title,
                source_url=resolved_source_url,
                segments=normalized_segments,
                compile_provider=compile_provider,
                api_key=api_key,
                model=model,
                max_chunk_workers=max_chunk_workers,
                max_concurrent_requests=max_concurrent_requests,
                fast_map_mode=fast_map_mode,
                split_map_mode=split_map_mode,
                fast_reduce_mode=fast_reduce_mode,
                lite_map_mode=lite_map_mode,
            )
            return _dossier_from_payload(compiled)
        except Exception:
            if normalized_compile_mode == "model":
                raise
    anchors = _build_anchors(normalized_segments)
    units = _build_semantic_units(normalized_segments, anchors=anchors, fallback=resolved_lecture_title)
    atoms = [_atom_from_unit(unit, index=index, lecture_id=resolved_lecture_id or "lecture") for index, unit in enumerate(units, start=1)]
    atoms = filter_lite_quality_atoms(atoms)
    relations = _relations_from_atoms(atoms)
    review_questions = [_review_question(atom) for atom in atoms[:6]]
    prerequisites = _prerequisites_from_atoms(atoms)
    pitfalls = _pitfalls_from_atoms(atoms)
    minimal_checks = _minimal_checks_from_questions(review_questions, atoms)
    minimal_examples = _minimal_examples_from_atoms(atoms)
    sections = _sections_from_atoms(atoms)
    lecture_summary = _lecture_summary(resolved_lecture_title, atoms, normalized_segments)
    tutoring_payload = enrich_tutoring_fields(
        tutoring_payload={
            "review_questions": review_questions,
            "prerequisites": prerequisites,
            "pitfalls": pitfalls,
            "minimal_checks": minimal_checks,
            "minimal_examples": minimal_examples,
        },
        course_name=resolved_course_title,
        lecture_title=resolved_lecture_title,
        atoms=atoms,
        relations=relations,
        anchors=anchors,
    )
    return LiteLectureDossier(
        course_title=resolved_course_title,
        lecture_id=resolved_lecture_id,
        lecture_title=resolved_lecture_title,
        source_url=resolved_source_url,
        lecture_summary=lecture_summary,
        sections=sections,
        anchors=anchors,
        atoms=atoms,
        relations=relations,
        review_questions=list(tutoring_payload.get("review_questions") or review_questions),
        prerequisites=[dict(item) for item in tutoring_payload.get("prerequisites") or prerequisites if isinstance(item, dict)],
        pitfalls=[dict(item) for item in tutoring_payload.get("pitfalls") or pitfalls if isinstance(item, dict)],
        minimal_checks=[dict(item) for item in tutoring_payload.get("minimal_checks") or minimal_checks if isinstance(item, dict)],
        minimal_examples=[dict(item) for item in tutoring_payload.get("minimal_examples") or minimal_examples if isinstance(item, dict)],
        followup_scaffold=[dict(item) for item in tutoring_payload.get("followup_scaffold") or [] if isinstance(item, dict)],
        feedback_routes=[dict(item) for item in tutoring_payload.get("feedback_routes") or [] if isinstance(item, dict)],
        search_hooks=[dict(item) for item in tutoring_payload.get("search_hooks") or [] if isinstance(item, dict)],
        provider="course2knowledge_lite_child_adapter",
        compile_source="deterministic_fallback",
    )


def _dossier_from_payload(payload: dict[str, Any]) -> LiteLectureDossier:
    return LiteLectureDossier(
        course_title=str(payload.get("course_title") or payload.get("course_name") or ""),
        lecture_id=str(payload.get("lecture_id") or ""),
        lecture_title=str(payload.get("lecture_title") or ""),
        source_url=str(payload.get("source_url") or ""),
        lecture_summary=str(payload.get("lecture_summary") or ""),
        sections=[dict(item) for item in payload.get("sections") or [] if isinstance(item, dict)],
        anchors=[dict(item) for item in payload.get("anchors") or [] if isinstance(item, dict)],
        atoms=[dict(item) for item in payload.get("atoms") or [] if isinstance(item, dict)],
        relations=[dict(item) for item in payload.get("relations") or [] if isinstance(item, dict)],
        review_questions=[str(item) for item in payload.get("review_questions") or [] if str(item).strip()],
        prerequisites=[dict(item) for item in payload.get("prerequisites") or [] if isinstance(item, dict)],
        pitfalls=[dict(item) for item in payload.get("pitfalls") or [] if isinstance(item, dict)],
        minimal_checks=[dict(item) for item in payload.get("minimal_checks") or [] if isinstance(item, dict)],
        minimal_examples=[dict(item) for item in payload.get("minimal_examples") or [] if isinstance(item, dict)],
        followup_scaffold=[dict(item) for item in payload.get("followup_scaffold") or [] if isinstance(item, dict)],
        feedback_routes=[dict(item) for item in payload.get("feedback_routes") or [] if isinstance(item, dict)],
        search_hooks=[dict(item) for item in payload.get("search_hooks") or [] if isinstance(item, dict)],
        provider=str(payload.get("provider") or "course2knowledge_lite_model_compile"),
        compile_source=str(payload.get("compile_source") or "model_map_reduce"),
    )


def build_lite_knowledge_atom_specs(
    text: str,
    *,
    fallback: str,
    segment_id: str = "",
) -> list[dict[str, Any]]:
    segment = {
        "segment_id": segment_id,
        "lecture_id": "",
        "start_seconds": 0.0,
        "end_seconds": 0.0,
        "text": text,
    }
    dossier = build_lite_lecture_dossier(
        lecture={"lecture_id": "", "title": fallback, "source_url": ""},
        segments=[segment],
        lecture_title=fallback,
        compile_mode="fallback",
        compile_provider=None,
    )
    return [_atom_to_card_spec(atom) for atom in dossier.atoms]


def render_lite_lecture_markdown(
    dossier: LiteLectureDossier | dict[str, Any],
    *,
    import_run_id: str = "",
) -> str:
    payload = dossier.to_dict() if isinstance(dossier, LiteLectureDossier) else dict(dossier)
    payload.setdefault("provider", "course2knowledge_lite_child_adapter")
    payload.setdefault("subtitle_source_kind", "transcript_segments")
    payload.setdefault("course_name", payload.get("course_title", ""))
    payload.setdefault("artifact_ref", f"sqlite://lecture_dossier/{payload.get('lecture_id', '')}")
    context = build_markdown_render_context(
        course_name=str(payload.get("course_name") or payload.get("course_title") or ""),
        lecture_id=str(payload.get("lecture_id") or ""),
        lecture_title=str(payload.get("lecture_title") or ""),
        source_url=str(payload.get("source_url") or ""),
        provider=str(payload.get("provider") or "course2knowledge_lite_child_adapter"),
        subtitle_source_kind=str(payload.get("subtitle_source_kind") or "transcript_segments"),
        artifact_ref=str(payload.get("artifact_ref") or ""),
        dossier=payload,
    )
    rendered = render_lecture_markdown(context)
    if import_run_id:
        rendered += f"\n\n导入批次: `{import_run_id}`\n"
    return rendered


def lite_atom_quality(card_or_atom: dict[str, Any]) -> dict[str, Any]:
    title = str(card_or_atom.get("canonical_title") or card_or_atom.get("title") or "").strip()
    summary = str(card_or_atom.get("summary") or "").strip()
    body = str(card_or_atom.get("body_markdown") or card_or_atom.get("body") or "").strip()
    questions = [str(item).strip() for item in card_or_atom.get("review_questions") or [] if str(item).strip()]
    reasons: list[str] = []
    if not title:
        reasons.append("missing_title")
    if _is_low_information_text(title):
        reasons.append("low_information_title")
    if not summary and not body:
        reasons.append("missing_summary_or_body")
    if not questions:
        reasons.append("missing_review_question")
    if len(_compact_text(title)) < 2:
        reasons.append("title_too_short")
    if len(_compact_text(title)) <= 3 and title not in {"RAG", "Agent", "MCP"}:
        reasons.append("title_too_generic")
    if _looks_like_course_logistics(title + " " + summary + " " + body):
        reasons.append("course_logistics")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "title": title,
    }


def is_lite_atom_quality_pass(card_or_atom: dict[str, Any]) -> bool:
    return bool(lite_atom_quality(card_or_atom).get("passed"))


def filter_lite_quality_atoms(atoms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(atom) for atom in atoms if lite_atom_quality(atom).get("passed")]


def _normalize_segments(segments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(segments, start=1):
        if not isinstance(raw, dict):
            continue
        text = _compact_text(raw.get("text", ""))
        if not text:
            continue
        normalized.append(
            {
                "line_id": index,
                "segment_id": str(raw.get("segment_id") or f"seg_{index:05d}").strip(),
                "lecture_id": str(raw.get("lecture_id") or "").strip(),
                "start_seconds": float(raw.get("start_seconds") or 0.0),
                "end_seconds": float(raw.get("end_seconds") or raw.get("start_seconds") or 0.0),
                "text": text,
            }
        )
    return normalized


def _build_anchors(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or "").strip()
        if _is_low_information_text(text):
            continue
        anchor_id = f"anc_{index:03d}"
        anchors.append(
            {
                "anchor_id": anchor_id,
                "modality": "subtitle",
                "source_line_ids": [int(segment.get("line_id") or index)],
                "start_timestamp": format_timestamp_anchor(segment.get("start_seconds") or 0.0),
                "end_timestamp": format_timestamp_anchor(segment.get("end_seconds") or segment.get("start_seconds") or 0.0),
                "suggested_screenshot_timestamp": format_timestamp_anchor(segment.get("start_seconds") or 0.0),
                "evidence_quote": _truncate(text, 96),
                "confidence": 0.72,
                "segment_id": str(segment.get("segment_id") or ""),
                "source_segment_ids": [str(segment.get("segment_id") or "")],
            }
        )
    return anchors


def _build_semantic_units(
    segments: list[dict[str, Any]],
    *,
    anchors: list[dict[str, Any]],
    fallback: str,
) -> list[dict[str, Any]]:
    anchor_by_line = {
        int((anchor.get("source_line_ids") or [0])[0] or 0): anchor
        for anchor in anchors
    }
    units: list[dict[str, Any]] = []
    for segment in segments:
        line_id = int(segment.get("line_id") or 0)
        anchor = anchor_by_line.get(line_id)
        if anchor is None:
            continue
        for piece in _split_teachable_text(str(segment.get("text") or "")):
            cleaned = _clean_unit_text(piece)
            if _is_low_information_text(cleaned):
                continue
            units.append(
                {
                    "text": cleaned,
                    "segment_ids": [str(segment.get("segment_id") or "")],
                    "anchor_ids": [str(anchor.get("anchor_id") or "")],
                    "score": _unit_signal_score(cleaned),
                }
            )
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in sorted(units, key=lambda item: (-float(item["score"]), str(item["text"]))):
        key = _dedupe_key(str(unit["text"]))
        if key in seen:
            continue
        seen.add(key)
        merged.append(unit)
        if len(merged) >= 8:
            break
    if not merged and fallback:
        cleaned = _clean_unit_text(fallback)
        if cleaned and not _is_low_information_text(cleaned):
            merged.append({"text": cleaned, "segment_ids": [], "anchor_ids": [], "score": 1.0})
    return sorted(merged, key=lambda item: ((item.get("segment_ids") or [""])[0], str(item.get("text") or "")))


def _split_teachable_text(text: str) -> list[str]:
    cleaned = _compact_text(text)
    if not cleaned:
        return []
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        pieces = [item.strip() for item in _SENTENCE_SPLIT_PATTERN.split(cleaned) if item.strip()]
    else:
        pieces = [item.strip() for item in re.split(r"(?<=[.!?;])\s+", cleaned) if item.strip()]
    if not pieces:
        pieces = [cleaned]
    expanded: list[str] = []
    for piece in pieces:
        if len(piece) <= 120:
            expanded.append(piece)
            continue
        clauses = [item.strip() for item in re.split(r"[，,；;]", piece) if item.strip()]
        expanded.extend(clauses or [piece])
    return expanded


def _atom_from_unit(unit: dict[str, Any], *, index: int, lecture_id: str) -> dict[str, Any]:
    text = _localize_text(str(unit.get("text") or ""))
    title = _title_from_text(text, fallback=f"知识点 {index}")
    atom_id_seed = f"{lecture_id}::{index}::{title}"
    atom_id = f"atom_{hashlib.sha1(atom_id_seed.encode('utf-8')).hexdigest()[:12]}"
    tags = _tags_from_text(text)
    return {
        "atom_id": atom_id,
        "canonical_title": title,
        "atom_type": _atom_type(text),
        "summary": _truncate(text, 120),
        "body_markdown": _body_markdown(text, title=title, tags=tags),
        "aliases": [],
        "tags": tags,
        "anchor_ids": list(unit.get("anchor_ids") or []),
        "source_anchor_id": str((unit.get("anchor_ids") or [""])[0] or ""),
        "source_segment_ids": list(unit.get("segment_ids") or []),
        "cross_references": [],
        "review_questions": [_review_question({"canonical_title": title, "atom_type": _atom_type(text)})],
        "status": "locked",
        "status_lite": "locked",
        "confidence": min(0.9, max(0.62, 0.58 + float(unit.get("score") or 0.0) / 10.0)),
        "artifact_ref": "",
    }


def _sections_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for atom in atoms[:5]:
        title = str(atom.get("canonical_title") or "").strip()
        if not title:
            continue
        sections.append(
            {
                "heading": title,
                "body": str(atom.get("summary") or atom.get("body_markdown") or "").strip(),
                "anchor_ids": list(atom.get("anchor_ids") or []),
            }
        )
    return sections


def _relations_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for left, right in zip(atoms, atoms[1:], strict=False):
        source = str(left.get("atom_id") or left.get("canonical_title") or "")
        target = str(right.get("atom_id") or right.get("canonical_title") or "")
        if not source or not target:
            continue
        relations.append(
            {
                "relation_id": f"{source}->{target}:sequence",
                "source_atom_id": source,
                "target_atom_id": target,
                "relation_type": "sequence",
                "anchor_ids": _unique_str_list(list(left.get("anchor_ids") or []) + list(right.get("anchor_ids") or [])),
                "evidence_quote": str(right.get("summary") or "")[:80],
                "confidence": 0.64,
            }
        )
    return relations


def _lecture_summary(lecture_title: str, atoms: list[dict[str, Any]], segments: list[dict[str, Any]]) -> str:
    if atoms:
        titles = "、".join(str(atom.get("canonical_title") or "") for atom in atoms[:3] if atom.get("canonical_title"))
        if titles:
            return f"本讲围绕 {titles} 展开，重点是把课程材料整理成可复述、可追问、可用证据支撑的知识单元。"
    for segment in segments:
        text = _clean_unit_text(str(segment.get("text") or ""))
        if text and not _is_low_information_text(text):
            return _truncate(_localize_text(text), 140)
    return f"本讲需要围绕「{lecture_title}」补齐可检索的课程证据。"


def _prerequisites_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": str(atom.get("canonical_title") or ""),
            "why_it_matters": str(atom.get("summary") or ""),
            "anchor_ids": list(atom.get("anchor_ids") or []),
        }
        for atom in atoms[:3]
        if str(atom.get("canonical_title") or "").strip()
    ]


def _pitfalls_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pitfalls: list[dict[str, Any]] = []
    for atom in atoms:
        text = " ".join(
            [
                str(atom.get("canonical_title") or ""),
                str(atom.get("summary") or ""),
                str(atom.get("body_markdown") or ""),
            ]
        )
        if not any(marker in text for marker in ("误区", "错误", "混淆", "边界", "不能", "不适合")):
            continue
        pitfalls.append(
            {
                "title": str(atom.get("canonical_title") or ""),
                "why_wrong": str(atom.get("summary") or ""),
                "correction": "回到课程证据，说明它的适用前提、边界和最小例子。",
                "anchor_ids": list(atom.get("anchor_ids") or []),
            }
        )
        if len(pitfalls) >= 4:
            break
    return pitfalls


def _minimal_checks_from_questions(questions: list[str], atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index, question in enumerate(questions[:4]):
        atom = atoms[index] if index < len(atoms) else {}
        checks.append(
            {
                "prompt": question,
                "expected_focus": "需要说清定义或判断、课程证据、适用边界和一个最小例子。",
                "anchor_ids": list(atom.get("anchor_ids") or []),
            }
        )
    return checks


def _minimal_examples_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not atoms:
        return []
    atom = atoms[0]
    title = str(atom.get("canonical_title") or "最小例子")
    return [
        {
            "title": f"{title}的最小复述",
            "problem": str(atom.get("summary") or title),
            "steps": [
                "先用自己的话复述这个知识点解决什么问题。",
                "再指出课程中支撑它的证据或例子。",
                "最后说明它的适用边界。",
            ],
            "takeaway": "能完成这三步，才算从听过走向可迁移使用。",
            "anchor_ids": list(atom.get("anchor_ids") or []),
        }
    ]


def _atom_to_card_spec(atom: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(atom.get("canonical_title") or ""),
        "body": str(atom.get("body_markdown") or ""),
        "tags": list(atom.get("tags") or []),
        "atom_type": str(atom.get("atom_type") or "concept"),
        "summary": str(atom.get("summary") or ""),
        "review_questions": list(atom.get("review_questions") or []),
        "anchor_refs": list(atom.get("anchor_ids") or []),
        "confidence": float(atom.get("confidence") or 0.72),
        "status_lite": str(atom.get("status_lite") or atom.get("status") or "locked"),
    }


def _review_question(atom: dict[str, Any]) -> str:
    title = str(atom.get("canonical_title") or atom.get("title") or "这个知识点").strip()
    atom_type = str(atom.get("atom_type") or "").strip()
    if atom_type == "procedure":
        return f"你能按顺序说清「{title}」的关键步骤、前提和容易错的地方吗？"
    if atom_type == "contrast":
        return f"你能区分「{title}」里最容易混淆的两种情况，并给出判断依据吗？"
    return f"你能用自己的话说明「{title}」解决什么问题，并指出课程证据和适用边界吗？"


def _body_markdown(text: str, *, title: str, tags: list[str]) -> str:
    lines = [f"核心意思：{_truncate(text, 180)}"]
    if tags:
        lines.append(f"关键词：{'、'.join(tags[:8])}")
    lines.append("掌握标准：能脱离原句复述，并说明它解决的问题、课程证据、适用边界和一个最小例子。")
    return "\n".join(lines)


def _title_from_text(text: str, *, fallback: str) -> str:
    cleaned = _clean_unit_text(text)
    if not cleaned:
        return fallback
    if "可问答知识库" in cleaned:
        return "视频课程变成可问答知识库"
    for _, replacement in _ENGLISH_TECH_TRANSLATIONS:
        if replacement and replacement in cleaned:
            return replacement
    for pattern, replacement in _ENGLISH_TECH_TRANSLATIONS:
        if pattern.search(cleaned):
            return replacement
    clause = re.split(r"[。！？!?；;，,]", cleaned, maxsplit=1)[0].strip()
    clause = re.sub(r"^(什么是|为什么|如何|怎么|也就是说)", "", clause).strip()
    if not clause:
        clause = cleaned
    tags = _tags_from_text(clause)
    if len(clause) > 30 and tags:
        return "、".join(tags[:3]) + "的课程要点"
    return _truncate(clause, 32) or fallback


def _atom_type(text: str) -> str:
    lowered = str(text or "").lower()
    if any(term in lowered for term in ("pitfall", "mistake", "wrong", "误区", "错误", "陷阱")):
        return "pitfall"
    if any(term in lowered for term in ("step", "first", "second", "procedure", "步骤", "流程", "先", "再", "最后", "如何", "怎么")):
        return "procedure"
    if any(term in lowered for term in ("difference", "compare", "while", "区别", "对比", "边界", "vs")):
        return "contrast"
    if any(term in lowered for term in ("规则", "必须", "需要", "判断", "本质", "条件")):
        return "rule"
    if any(term in lowered for term in ("方法", "策略", "实现", "处理")):
        return "method"
    return "concept"


def _tags_from_text(text: str) -> list[str]:
    tags: list[str] = []
    for term in _CORE_TAG_TERMS:
        if _contains_tag_term(str(text or ""), term) and term not in tags:
            tags.append(term)
        if len(tags) >= 10:
            break
    for term in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", str(text or "")):
        if term.lower() in _ENGLISH_STOP_TAGS:
            continue
        if term not in tags:
            tags.append(term)
        if len(tags) >= 10:
            break
    return tags


def _unit_signal_score(text: str) -> float:
    cleaned = _compact_text(text)
    if not cleaned:
        return 0.0
    score = min(len(cleaned) / 18.0, 3.0)
    score += sum(1.0 for term in _CORE_TAG_TERMS if _contains_tag_term(cleaned, term))
    score += 1.0 if any(marker in cleaned for marker in ("因为", "所以", "如果", "需要", "能够", "用于", "解决", "区别", "关系")) else 0.0
    return score


def _is_low_information_text(text: str) -> bool:
    cleaned = _clean_unit_text(text)
    if not cleaned:
        return True
    if len(cleaned) <= 3:
        return True
    if any(pattern.search(cleaned) for pattern in _LOW_INFORMATION_PATTERNS):
        return True
    low_info_fragments = (
        "正式开始",
        "让我们",
        "分享的是",
        "先抛出结论",
        "自己的理解",
        "第一个视频当中",
    )
    if any(fragment in cleaned for fragment in low_info_fragments):
        return True
    if cleaned.endswith("这门课") and len(cleaned) <= 12:
        return True
    if _looks_like_course_logistics(cleaned):
        return True
    return False


def _looks_like_course_logistics(text: str) -> bool:
    cleaned = str(text or "")
    if not any(term in cleaned for term in _COURSE_LOGISTICS_TERMS):
        return False
    return not any(term in cleaned for term in _TEACHABLE_LOGISTICS_ALLOW_TERMS)


def _clean_unit_text(text: str) -> str:
    cleaned = _compact_text(text)
    previous = ""
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _DISCOURSE_PREFIX_PATTERN.sub("", cleaned).strip()
    for prefix in ("好下面", "那么", "我们", "那", "好"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned.strip("，。！？!?；;:： ")


def _localize_text(text: str) -> str:
    cleaned = _compact_text(text)
    if not cleaned:
        return ""
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        return cleaned
    localized = cleaned
    for pattern, replacement in _ENGLISH_TECH_TRANSLATIONS:
        localized = pattern.sub(replacement, localized)
    if not re.search(r"[\u4e00-\u9fff]", localized):
        tags = _tags_from_text(localized)
        if tags:
            localized = f"本段围绕 {'、'.join(tags[:4])} 展开，需要结合课程证据说明作用和边界。"
        else:
            localized = f"本段材料需要整理成可复述的课程知识：{localized}"
    return localized


def _dedupe_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", _compact_text(text).lower())[:48]


def _contains_tag_term(text: str, term: str) -> bool:
    haystack = str(text or "")
    if not haystack or not term:
        return False
    if re.fullmatch(r"[A-Za-z0-9_+-]+", term):
        return re.search(rf"(?<![A-Za-z0-9_+-]){re.escape(term)}(?![A-Za-z0-9_+-])", haystack, flags=re.IGNORECASE) is not None
    return term.lower() in haystack.lower()


def _unique_str_list(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _truncate(text: Any, limit: int) -> str:
    cleaned = _compact_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."


def _compact_text(text: Any) -> str:
    return _SPACE_PATTERN.sub(" ", str(text or "").strip())
