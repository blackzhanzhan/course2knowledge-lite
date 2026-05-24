from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_bilibili import BilibiliCollection, BilibiliVideoRef  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_store import (  # noqa: E402
    JsonCourseStore,
    SQLiteCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_lite_lecture_dossier,
    lite_atom_quality,
    render_lite_lecture_markdown,
    build_course_skeleton,
)
from course2knowledge_lite_store.store import _knowledge_atom_specs  # noqa: E402


class CourseStoreSkeletonTests(unittest.TestCase):
    def test_sqlite_merge_course_from_store_adds_new_course_without_deleting_existing_chat(self) -> None:
        with tempfile.TemporaryDirectory() as production_dir, tempfile.TemporaryDirectory() as source_dir:
            production_store = SQLiteCourseStore(production_dir)
            source_store = SQLiteCourseStore(source_dir)
            existing = build_course_skeleton(
                title="Existing course",
                source_url="https://www.bilibili.com/video/BVEXISTING",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVEXISTING",
                        "title": "Existing lecture",
                        "source_url": "https://www.bilibili.com/video/BVEXISTING",
                    }
                ],
                course_id="course_existing",
                now="2026-05-20T00:00:00Z",
            )
            incoming = build_course_skeleton(
                title="Incoming course",
                source_url="https://www.bilibili.com/video/BVINCOMING",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVINCOMING",
                        "title": "Incoming lecture",
                        "source_url": "https://www.bilibili.com/video/BVINCOMING",
                    }
                ],
                course_id="course_incoming",
                now="2026-05-20T00:01:00Z",
            )
            production_store.write_skeleton(existing)
            thread = production_store.create_chat_thread("course_existing", title="Keep me", thread_id="thread_keep")
            production_store.append_chat_message(str(thread["thread_id"]), "user", "Do not delete this")
            source_store.write_skeleton(incoming)
            lecture = incoming.lectures[0]
            source_store.write_transcript_segments(
                incoming.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::seg::1",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0,
                        end_seconds=8,
                        text="Incoming course evidence is complete enough for a note.",
                    )
                ],
            )
            source_store.create_note(incoming.course.course_id, lecture.lecture_id, "Incoming note", note_id="note_incoming")
            source_store.generate_knowledge_cards(
                incoming.course.course_id,
                lecture_id=lecture.lecture_id,
                overwrite=True,
                compile_mode="fallback",
                compile_provider=None,
            )
            source_store.create_import_run(
                run_id="run_incoming",
                course_id=incoming.course.course_id,
                source_url=incoming.course.source_url,
                status="completed",
                stage="ready_gate",
                total_lectures=1,
                completed_lectures=1,
            )
            source_store.append_import_event(
                "run_incoming",
                stage="ready_gate",
                status="completed",
                event_type="ready_gate",
                message="ready",
                payload={"ready": True},
            )

            result = production_store.merge_course_from_store(source_store, incoming.course.course_id)

            self.assertEqual(result["copied"]["courses"], 1)
            self.assertEqual({course["course_id"] for course in production_store.list_courses()}, {"course_existing", "course_incoming"})
            self.assertEqual(len(production_store.list_chat_messages("thread_keep")), 1)
            self.assertEqual(production_store.read_import_run("run_incoming")["course_id"], "course_incoming")
            self.assertEqual(production_store.summarize_import_readiness("course_incoming")["ready_lecture_count"], 1)

    def test_sqlite_merge_course_from_store_replaces_same_course_scope_only(self) -> None:
        with tempfile.TemporaryDirectory() as production_dir, tempfile.TemporaryDirectory() as source_dir:
            production_store = SQLiteCourseStore(production_dir)
            source_store = SQLiteCourseStore(source_dir)
            old_course = build_course_skeleton(
                title="Same course old",
                source_url="https://www.bilibili.com/video/BVSAME",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVSAME",
                        "title": "Old lecture",
                        "source_url": "https://www.bilibili.com/video/BVSAME?p=1",
                    }
                ],
                course_id="course_same",
                now="2026-05-20T00:00:00Z",
            )
            other_course = build_course_skeleton(
                title="Other course",
                source_url="https://www.bilibili.com/video/BVOTHER",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVOTHER",
                        "title": "Other lecture",
                        "source_url": "https://www.bilibili.com/video/BVOTHER",
                    }
                ],
                course_id="course_other",
                now="2026-05-20T00:00:00Z",
            )
            new_course = build_course_skeleton(
                title="Same course new",
                source_url="https://www.bilibili.com/video/BVSAME",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVSAME",
                        "title": "New lecture 1",
                        "source_url": "https://www.bilibili.com/video/BVSAME?p=1",
                    },
                    {
                        "sequence": 2,
                        "bvid": "BVSAME",
                        "title": "New lecture 2",
                        "source_url": "https://www.bilibili.com/video/BVSAME?p=2",
                    },
                ],
                course_id="course_same",
                now="2026-05-20T00:02:00Z",
            )
            production_store.write_skeleton(old_course)
            production_store.write_skeleton(other_course)
            source_store.write_skeleton(new_course)

            result = production_store.merge_course_from_store(source_store, "course_same")

            self.assertEqual(result["copied"]["lectures"], 2)
            self.assertEqual(production_store.read_course("course_same")["title"], "Same course new")
            self.assertEqual([lecture["title"] for lecture in production_store.read_lectures("course_same")], ["New lecture 1", "New lecture 2"])
            self.assertEqual(production_store.read_course("course_other")["title"], "Other course")

    def test_lite_dossier_filters_subtitle_fragments_before_atoms(self) -> None:
        lecture = {
            "lecture_id": "course_ds::lecture::002",
            "title": "1.0_开篇_数据结构在学什么",
            "source_url": "https://www.bilibili.com/video/BV1b7411N798?p=2",
        }
        fragments = [
            "好下面就让我们正式开始进入数据结构这门课",
            "那第一个视频当中",
            "我们要和大家分享的是数据结构这门课",
            "那我们先抛出结论",
            "这是我自己的理解",
            "数据结构这门课",
            "并且我们还要研究怎么用计算机更高效的来处理这些信息",
            "把现实世界的问题给信息化的例子",
            "怎么在计算机当中表示刚才我们所说到的这些信息呢",
            "我们只需要设置一个float型也就是浮点型的变量是不是就可以解决",
            "怎么把队列给信息化呢",
            "比如我们是不是可以定义一个数组然后在这个数组当中分别记录每一桌的人",
            "怎么表示这些用户互相关注这个逻辑关系呢",
            "在学了数据结构这门课之后大家就会知道怎么用程序代码把现实世界当中的问题给信息化",
            "在这门课当中我们还会研究怎么用计算机来高效地处理这些信息",
            "计算机组成原理这门课其实研究的就是计算机底层的这些硬件它是怎么工作的",
            "那操作系统这门课他要研究的就是这些操作系统它在背后是怎么工作的怎么管理你的手机管理你的电脑的",
            "计算机网络它实现了各个计算机或者计算机和手机之间的互联互通",
        ]
        segments = [
            {
                "segment_id": f"course_ds::lecture::002::seg::{index:05d}",
                "lecture_id": lecture["lecture_id"],
                "start_seconds": float(index * 4),
                "end_seconds": float(index * 4 + 3),
                "text": text,
            }
            for index, text in enumerate(fragments, start=1)
        ]

        dossier = build_lite_lecture_dossier(
            course={"title": "王道计算机考研 数据结构"},
            lecture=lecture,
            segments=segments,
            compile_mode="fallback",
            compile_provider=None,
        )
        titles = [atom["canonical_title"] for atom in dossier.atoms]
        rejected = {
            "好下面就让我们正式开始进入数据结构这门课",
            "那第一个视频当中",
            "我们要和大家分享的是数据结构这门课",
            "那我们先抛出结论",
            "这是我自己的理解",
            "数据结构这门课",
            "从而创造价值",
        }

        self.assertTrue(titles)
        self.assertTrue(rejected.isdisjoint(titles))
        self.assertGreaterEqual(len(dossier.anchors), 4)
        self.assertTrue(dossier.followup_scaffold)
        self.assertTrue(dossier.search_hooks)
        self.assertTrue(all(atom.get("anchor_ids") for atom in dossier.atoms[:3]))
        self.assertTrue(all(lite_atom_quality(atom)["passed"] for atom in dossier.atoms))

    def test_lite_dossier_rejects_course_logistics_and_canonicalizes_data_structure_atoms(self) -> None:
        lecture = {
            "lecture_id": "course_ds::lecture::003",
            "title": "1.1_数据结构的基本概念",
            "source_url": "https://www.bilibili.com/video/BV1b7411N798?p=3",
        }
        lines = [
            "我是王道考研系列课程的主讲人咸鱼学长",
            "而计算机网络会由楼楼学姐带大家来学习",
            "王道单科书在京东天猫当当等各大平台都有卖",
            "建议大家学完一个小节就完成一个小节的题目",
            "有助于我们自我检测对于基础知识的掌握情况",
            "数据是信息的载体，是描述客观事物的数字字符及能够输入到计算机中，并且被计算机程序识别和处理的符号集合",
            "因为计算机能够识别和处理的只有二进制数",
            "只要我们能够确定一个转换规则，其实都可以转换成二进制表示的形式",
            "那什么是数据元素呢，这是王道书给的定义",
            "每一波顾客的信息其实就是一个数据元素，而每个数据元素当中又会由多个数据项组成",
            "数据结构的三要素分别是逻辑结构、物理结构和数据的运算",
            "常见的会有四种逻辑结构关系，分别是集合、线性、树形和图状关系",
            "线性结构就是所有的数据元素穿成了一条线，这些数据元素之间都是一对一的关系",
            "树形结构不就是一对多的这种树形结构的关系吗",
            "图状结构或者叫网状结构，强调数据元素之间多对多的关系",
        ]
        segments = [
            {
                "segment_id": f"course_ds::lecture::003::seg::{index:05d}",
                "lecture_id": lecture["lecture_id"],
                "start_seconds": float(index * 5),
                "end_seconds": float(index * 5 + 4),
                "text": text,
            }
            for index, text in enumerate(lines, start=1)
        ]

        dossier = build_lite_lecture_dossier(
            course={"title": "王道计算机考研 数据结构"},
            lecture=lecture,
            segments=segments,
            compile_mode="fallback",
            compile_provider=None,
        )
        titles = [atom["canonical_title"] for atom in dossier.atoms]
        title_text = "\n".join(titles)

        self.assertNotIn("计算机网络会由楼楼学姐带大家来学习", title_text)
        self.assertNotIn("人手必备", title_text)
        self.assertNotIn("考研资讯", title_text)
        self.assertNotIn("什么的数据元素呢", title_text)
        self.assertNotIn("分别的逻辑结构", title_text)
        self.assertNotIn("不就的一对多", title_text)
        self.assertGreaterEqual(len(titles), 5)
        self.assertTrue(any("二进制" in title or "数据" in title for title in titles))
        self.assertTrue(any("逻辑结构" in title or "线性" in title or "关系" in title for title in titles))
        self.assertTrue(dossier.minimal_examples)
        self.assertTrue(dossier.followup_scaffold)
        self.assertTrue(all(lite_atom_quality(atom)["passed"] for atom in dossier.atoms))

    def test_lite_dossier_keeps_teachable_study_guidance_from_intro_lecture(self) -> None:
        lecture = {
            "lecture_id": "course_ds::lecture::001",
            "title": "0.0 课程白嫖指南",
            "source_url": "https://www.bilibili.com/video/BV1b7411N798?p=1",
        }
        lines = [
            "我是王道考研系列课程的主讲人咸鱼学长",
            "而计算机网络会由楼楼学姐带大家来学习",
            "王道单科书在京东天猫当当等各大平台都有卖",
            "建议大家学完一个小节就完成一个小节的题目",
            "特别是小题部分，也就是选择题部分，有助于我们自我检测对于基础知识的掌握情况",
            "而大题部分通常来说考察的会比较综合，并且题量也比较大",
            "我们在第一次学习的时候，有选择的做一些简单的大题，对大题的考察重点还有考察形式有一个初步的认识就可以了",
            "希望大家不要只是听我们的视频课，也需要在王道书上做相应的笔记，并且完成相应的课后习题",
            "动手训练的过程是非常重要的",
        ]
        segments = [
            {
                "segment_id": f"course_ds::lecture::001::seg::{index:05d}",
                "lecture_id": lecture["lecture_id"],
                "start_seconds": float(index * 5),
                "end_seconds": float(index * 5 + 4),
                "text": text,
            }
            for index, text in enumerate(lines, start=1)
        ]

        dossier = build_lite_lecture_dossier(
            course={"title": "王道计算机考研 数据结构"},
            lecture=lecture,
            segments=segments,
            compile_mode="fallback",
            compile_provider=None,
        )
        titles = [atom["canonical_title"] for atom in dossier.atoms]
        title_text = "\n".join(titles)

        self.assertNotIn("计算机网络会由楼楼学姐带大家来学习", title_text)
        self.assertNotIn("王道单科书", title_text)
        self.assertGreaterEqual(len(titles), 4)
        self.assertTrue(any("题" in title or "练习" in title or "自测" in title for title in titles))
        self.assertTrue(any("笔记" in title or "视频" in title for title in titles))
        self.assertTrue(dossier.review_questions)
        self.assertTrue(dossier.followup_scaffold)
        self.assertTrue(all(lite_atom_quality(atom)["passed"] for atom in dossier.atoms))

    def test_lite_atom_specs_split_teachable_units_and_clean_tags(self) -> None:
        zh_atoms = _knowledge_atom_specs(
            "第一段介绍课程目标。第二段说明 RAG 和 Agent 的区别。第三段总结如何把视频课程变成可问答知识库。",
            fallback="课程导入",
        )
        en_atoms = _knowledge_atom_specs(
            "This lecture focuses on RAG accuracy optimization. Step one is checking retrieval recall. Step two is improving chunking and reranking. Step three is verifying whether the final answer is supported by cited course evidence.",
            fallback="RAG accuracy",
        )

        self.assertGreaterEqual(len(zh_atoms), 3)
        self.assertTrue(any("课程" in atom["title"] or "目标" in atom["title"] for atom in zh_atoms))
        self.assertTrue(any("RAG" in atom["tags"] for atom in zh_atoms))
        self.assertTrue(any(atom["atom_type"] in {"contrast", "concept", "method"} for atom in zh_atoms))
        self.assertTrue(zh_atoms[1]["review_questions"])
        self.assertGreaterEqual(len(en_atoms), 3)
        tag_text = " ".join(tag for atom in en_atoms for tag in atom["tags"])
        for noisy in ("This", "lecture", "Step", "one", "is", "and"):
            self.assertNotIn(noisy, tag_text.split())
        self.assertTrue(any("retrieval" in atom["tags"] or "检索" in atom["tags"] for atom in en_atoms))

    def test_english_transcript_generates_chinese_lite_dossier_atoms_and_note(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG accuracy",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]
        segments = [
            {
                "segment_id": f"{lecture.lecture_id}::seg::00001",
                "lecture_id": lecture.lecture_id,
                "start_seconds": 0.0,
                "end_seconds": 4.0,
                "text": "This lecture focuses on RAG accuracy optimization.",
            },
            {
                "segment_id": f"{lecture.lecture_id}::seg::00002",
                "lecture_id": lecture.lecture_id,
                "start_seconds": 4.0,
                "end_seconds": 8.0,
                "text": "Step one is checking retrieval recall. Step two is improving chunking and reranking.",
            },
            {
                "segment_id": f"{lecture.lecture_id}::seg::00003",
                "lecture_id": lecture.lecture_id,
                "start_seconds": 8.0,
                "end_seconds": 12.0,
                "text": "Step three is verifying whether the final answer is supported by cited course evidence.",
            },
        ]

        dossier = build_lite_lecture_dossier(
            course=skeleton.course.to_dict(),
            lecture=lecture.to_dict(),
            segments=segments,
            compile_mode="fallback",
            compile_provider=None,
        )
        markdown = render_lite_lecture_markdown(dossier, import_run_id="run_test")

        self.assertIn("## 总摘要", markdown)
        self.assertIn("## 知识原子", markdown)
        self.assertIn("## 复习问题", markdown)
        self.assertIn("## 证据锚点", markdown)
        self.assertIn("RAG 准确率优化", markdown)
        self.assertIn("检查检索召回", markdown)
        self.assertIn("改进切片与重排", markdown)
        self.assertIn("核验最终答案是否由课程证据支撑", markdown)
        self.assertIn("## 追问脚手架", markdown)
        self.assertIn("## 答错分流", markdown)
        self.assertNotIn("## Transcript Evidence", markdown)
        self.assertTrue(dossier.review_questions)
        self.assertTrue(all("你能" in question for question in dossier.review_questions[:3]))
        self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", atom["canonical_title"]) for atom in dossier.atoms[:3]))

    def test_bilibili_collection_video_refs_write_course_skeleton(self) -> None:
        collection = BilibiliCollection(
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            title="合集·AI大模型面试-全套合集",
            videos=[
                BilibiliVideoRef(
                    sequence=i,
                    bvid=f"BV{i:08d}",
                    title=f"Lecture {i}",
                    source_url=f"https://www.bilibili.com/video/BV{i:08d}",
                )
                for i in range(1, 31)
            ],
        )

        skeleton = build_course_skeleton(
            title=collection.title,
            source_url=collection.source_url,
            video_refs=collection.videos,
            now="2026-05-14T00:00:00Z",
        )

        self.assertEqual(skeleton.course.import_status, "accepted")
        self.assertEqual(len(skeleton.lectures), 30)
        self.assertEqual(skeleton.lectures[0].sequence, 1)
        self.assertEqual(skeleton.lectures[0].source_id, "BV00000001")
        self.assertEqual(skeleton.import_status.stage, "collection_expanded")
        self.assertEqual(skeleton.import_status.completed_lectures, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = JsonCourseStore(temp_dir).write_skeleton(skeleton)
            store = JsonCourseStore(temp_dir)
            course = store.read_course(skeleton.course.course_id)
            lectures = store.read_lectures(skeleton.course.course_id)
            status = store.read_import_status(skeleton.import_status.import_id)

        self.assertTrue(paths["course"].endswith("course.json"))
        self.assertEqual(course["title"], "合集·AI大模型面试-全套合集")
        self.assertEqual(len(lectures), 30)
        self.assertEqual(lectures[-1]["source_url"], "https://www.bilibili.com/video/BV00000030")
        self.assertEqual(status["total_lectures"], 30)

    def test_handoff_imports_collection_skeleton_to_store(self) -> None:
        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            del api_url, params, referer
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "AI interview course"},
                    "archives": [
                        {"bvid": "BV00000001", "title": "Lecture 1"},
                        {"bvid": "BV00000002", "title": "Lecture 2"},
                    ],
                    "page": {"total": 2},
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_fetch_json,
            )
            store = SQLiteCourseStore(temp_dir)
            lectures = store.read_lectures(result["course"]["course_id"])

        self.assertEqual(result["course"]["title"], "AI interview course")
        self.assertEqual(result["import_status"]["stage"], "collection_expanded")
        self.assertEqual(len(result["lectures"]), 2)
        self.assertEqual(len(lectures), 2)
        self.assertEqual(lectures[1]["source_id"], "BV00000002")

    def test_sqlite_store_round_trips_public_course_records(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            paths = store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            card = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"][0]
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            note = store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "RAG uses retrieved evidence.",
                note_id="note_sqlite",
                now="2026-05-14T01:00:00Z",
            )
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "card",
                card["card_id"],
                bookmark_id="bookmark_sqlite",
                now="2026-05-14T01:10:00Z",
            )
            progress = store.set_reading_progress(
                skeleton.course.course_id,
                lecture.lecture_id,
                "read",
                now="2026-05-14T01:15:00Z",
            )

            persisted = SQLiteCourseStore(temp_dir)
            course = persisted.read_course(skeleton.course.course_id)
            lectures = persisted.read_lectures(skeleton.course.course_id)
            search_hits = persisted.search_transcripts(skeleton.course.course_id, "RAG Agent")
            visuals = persisted.list_visual_evidence(course_id=skeleton.course.course_id, query="evidence")
            notes = persisted.list_notes(course_id=skeleton.course.course_id)
            bookmarks = persisted.list_bookmarks(course_id=skeleton.course.course_id)
            conn = sqlite3.connect(paths["database"])
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            finally:
                conn.close()

        self.assertTrue(paths["database"].endswith("course2knowledge-lite.sqlite3"))
        self.assertEqual(course["title"], "AI interview course")
        self.assertEqual(lectures[0]["read_status"], "read")
        self.assertEqual(search_hits[0]["citation"]["segment_id"], segment_id)
        self.assertEqual(visuals[0]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(note["note_id"], "note_sqlite")
        self.assertEqual(bookmark["target_id"], card["card_id"])
        self.assertEqual(progress["status"], "read")
        self.assertEqual(notes[0]["note_id"], "note_sqlite")
        self.assertEqual(bookmarks[0]["bookmark_id"], "bookmark_sqlite")
        self.assertTrue(
            {
                "courses",
                "lectures",
                "transcript_segments",
                "knowledge_cards",
                "visual_evidence",
                "notes",
                "bookmarks",
                "reading_progress",
                "import_statuses",
                "import_runs",
                "import_events",
                "import_artifacts",
            }.issubset(tables)
        )

    def test_sqlite_import_run_events_artifacts_and_readiness_gate(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Chunking",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            run = store.create_import_run(
                course_id=skeleton.course.course_id,
                source_url=skeleton.course.source_url,
                status="running",
                stage="source_acquisition",
                total_lectures=2,
                now="2026-05-14T00:01:00Z",
            )
            store.append_import_event(
                run["run_id"],
                stage="source_acquisition",
                status="completed",
                event_type="lecture_completed",
                message="lecture 1 ready",
                payload={"lecture_id": lecture.lecture_id},
                now="2026-05-14T00:02:00Z",
            )
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::manual::00001",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            note = store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "# RAG and Agent\n\nRAG retrieves evidence.",
                note_id="generated_note_001",
                now="2026-05-14T00:03:00Z",
            )
            cards = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"]
            store.record_import_artifact(
                run_id=run["run_id"],
                course_id=skeleton.course.course_id,
                lecture_id=lecture.lecture_id,
                artifact_type="lesson_note",
                artifact_ref=f"sqlite://notes/{note['note_id']}",
                status="ready",
                payload={"note_id": note["note_id"]},
                now="2026-05-14T00:04:00Z",
            )
            readiness = store.summarize_import_readiness(skeleton.course.course_id)
            events = store.list_import_events(run["run_id"])
            artifacts = store.list_import_artifacts(run_id=run["run_id"])

        self.assertEqual(events[0]["event_type"], "lecture_completed")
        self.assertEqual(artifacts[0]["artifact_type"], "lesson_note")
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["ready_lecture_count"], 1)
        self.assertEqual(readiness["missing_lecture_count"], 1)
        self.assertEqual(readiness["total_atom_count"], len(cards))
        self.assertGreater(readiness["total_gate_count"], 0)
        self.assertEqual(readiness["lectures"][0]["status"], "ready")
        self.assertIn("transcript", readiness["lectures"][1]["missing"])

    def test_sqlite_backfills_import_run_ledger_from_existing_readiness(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Chunking",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::manual::00001",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "# RAG and Agent\n\nRAG retrieves evidence.",
                note_id="generated_note_001",
                now="2026-05-14T00:03:00Z",
            )
            store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )
            run = store.backfill_import_run_from_readiness(
                skeleton.course.course_id,
                now="2026-05-14T00:05:00Z",
            )
            repeated_run = store.backfill_import_run_from_readiness(skeleton.course.course_id)
            runs = store.list_import_runs(course_id=skeleton.course.course_id)
            events = store.list_import_events(run["run_id"])
            artifacts = store.list_import_artifacts(run_id=run["run_id"])
            readiness = store.summarize_import_readiness(skeleton.course.course_id)

        self.assertEqual(run["run_id"], repeated_run["run_id"])
        self.assertEqual(len(runs), 1)
        self.assertEqual(run["status"], "partial")
        self.assertEqual(run["stage"], "ready_gate_blocked")
        self.assertEqual(run["completed_lectures"], 1)
        self.assertEqual(run["failed_lectures"], 1)
        self.assertEqual(readiness["latest_run"]["run_id"], run["run_id"])
        self.assertEqual(events[-1]["event_type"], "ready_gate")
        self.assertTrue(any(event["event_type"] == "lecture_completed" for event in events))
        self.assertTrue(any(event["event_type"] == "lecture_not_ready" for event in events))
        self.assertTrue(any(artifact["artifact_type"] == "transcript" for artifact in artifacts))
        self.assertTrue(any(artifact["artifact_type"] == "lecture_failure" for artifact in artifacts))

    def test_lecture_reader_and_search_consume_transcript_segments(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Tool calling",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture_id = skeleton.lectures[0].lecture_id

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture_id}::manual::00001",
                        lecture_id=lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="This segment explains the difference between RAG and Agent workflows.",
                    )
                ],
            )

            reader = store.read_lecture_reader(skeleton.course.course_id, lecture_sequence=1)
            results = store.search_transcripts(skeleton.course.course_id, "RAG Agent")

        self.assertTrue(reader["has_transcript"])
        self.assertEqual(reader["segment_count"], 1)
        self.assertEqual(reader["lecture"]["title"], "RAG and Agent")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["citation"]["lecture_sequence"], 1)
        self.assertEqual(results[0]["citation"]["segment_id"], f"{lecture_id}::manual::00001")
        self.assertIn("RAG", results[0]["snippet"])

    def test_transcript_coverage_summarizes_covered_and_missing_lectures(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "RAG accuracy",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
                {
                    "sequence": 3,
                    "bvid": "BV00000003",
                    "title": "Learning route",
                    "source_url": "https://www.bilibili.com/video/BV00000003",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            for lecture in skeleton.lectures[:2]:
                store.write_transcript_segments(
                    skeleton.course.course_id,
                    lecture.lecture_id,
                    [
                        TranscriptSegmentRecord(
                            segment_id=f"{lecture.lecture_id}::manual::00001",
                            lecture_id=lecture.lecture_id,
                            start_seconds=0.0,
                            end_seconds=6.0,
                            text=f"{lecture.title} transcript segment",
                        )
                    ],
                )

            coverage = store.summarize_transcript_coverage(skeleton.course.course_id)

        self.assertEqual(coverage["lecture_count"], 3)
        self.assertEqual(coverage["covered_lecture_count"], 2)
        self.assertEqual(coverage["missing_lecture_count"], 1)
        self.assertEqual(coverage["total_segment_count"], 2)
        self.assertAlmostEqual(coverage["coverage_ratio"], 0.6667)
        self.assertTrue(coverage["lectures"][0]["has_transcript"])
        self.assertFalse(coverage["lectures"][2]["has_transcript"])

    def test_learning_state_round_trips_notes_bookmarks_and_progress(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves course evidence, while an Agent plans actions and calls tools.",
                    )
                ],
            )

            note = store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "RAG uses retrieved evidence.",
                note_id="note_test",
                now="2026-05-14T01:00:00Z",
            )
            updated_note = store.update_note(
                skeleton.course.course_id,
                "note_test",
                "RAG grounds answers in retrieved evidence.",
                now="2026-05-14T01:05:00Z",
            )
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "segment",
                segment_id,
                bookmark_id="bookmark_test",
                now="2026-05-14T01:10:00Z",
            )
            progress = store.set_reading_progress(
                skeleton.course.course_id,
                lecture.lecture_id,
                "read",
                now="2026-05-14T01:15:00Z",
            )
            persisted = JsonCourseStore(temp_dir)
            persisted_notes = persisted.list_notes(course_id=skeleton.course.course_id, lecture_id=lecture.lecture_id)
            persisted_bookmarks = persisted.list_bookmarks(course_id=skeleton.course.course_id)
            persisted_progress = persisted.get_reading_progress(skeleton.course.course_id, lecture.lecture_id)
            lectures = persisted.read_lectures(skeleton.course.course_id)

        self.assertEqual(note["note_id"], "note_test")
        self.assertEqual(updated_note["body"], "RAG grounds answers in retrieved evidence.")
        self.assertEqual(bookmark["target_id"], segment_id)
        self.assertEqual(progress["status"], "read")
        self.assertEqual(len(persisted_notes), 1)
        self.assertEqual(persisted_notes[0]["updated_at"], "2026-05-14T01:05:00Z")
        self.assertEqual(len(persisted_bookmarks), 1)
        self.assertEqual(persisted_progress["status"], "read")
        self.assertEqual(lectures[0]["read_status"], "read")

    def test_source_linked_knowledge_cards_generate_list_read_and_bookmark(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Evaluation",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        first_lecture = skeleton.lectures[0]
        second_lecture = skeleton.lectures[1]
        first_segment_id = f"{first_lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                first_lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=first_segment_id,
                        lecture_id=first_lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            store.write_transcript_segments(
                skeleton.course.course_id,
                second_lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{second_lecture.lecture_id}::manual::00001",
                        lecture_id=second_lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="Evaluation checks whether answers stay grounded in course transcripts.",
                    )
                ],
            )

            result = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )
            cards = store.list_knowledge_cards(course_id=skeleton.course.course_id)
            first_card = store.read_knowledge_card(skeleton.course.course_id, cards[0]["card_id"])
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "card",
                first_card["card_id"],
                bookmark_id="bookmark_card",
                now="2026-05-14T01:20:00Z",
            )
            lecture_cards = store.list_knowledge_cards(
                course_id=skeleton.course.course_id,
                lecture_id=first_lecture.lecture_id,
            )
            first_only = store.generate_knowledge_cards(
                skeleton.course.course_id,
                lecture_id=first_lecture.lecture_id,
                overwrite=True,
                compile_mode="fallback",
                compile_provider=None,
            )
            regenerated = store.generate_knowledge_cards(
                skeleton.course.course_id,
                overwrite=False,
                compile_mode="fallback",
                compile_provider=None,
            )

        self.assertGreaterEqual(result["generated_card_count"], 2)
        self.assertEqual(result["card_count"], result["generated_card_count"])
        self.assertEqual(len(cards), result["card_count"])
        self.assertEqual(first_card["source_segment_ids"], [first_segment_id])
        self.assertEqual(first_card["course_id"], skeleton.course.course_id)
        self.assertIn("RAG", first_card["tags"])
        self.assertIn(first_card["atom_type"], {"concept", "contrast", "procedure"})
        self.assertTrue(first_card["summary"])
        self.assertTrue(first_card["review_questions"])
        self.assertEqual(first_card["status_lite"], "locked")
        self.assertEqual(bookmark["target_type"], "card")
        self.assertEqual(bookmark["target_id"], first_card["card_id"])
        self.assertGreaterEqual(len(lecture_cards), 1)
        self.assertEqual(first_only["card_count"], result["card_count"])
        self.assertGreaterEqual(first_only["generated_card_count"], 1)
        self.assertEqual(regenerated["card_count"], result["card_count"])

    def test_sqlite_generated_cards_are_chinese_first_for_english_transcripts(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG accuracy",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::seg::00001",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=4.0,
                        text="This lecture focuses on RAG accuracy optimization.",
                    ),
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::seg::00002",
                        lecture_id=lecture.lecture_id,
                        start_seconds=4.0,
                        end_seconds=8.0,
                        text="Step one is checking retrieval recall. Step two is improving chunking and reranking.",
                    ),
                ],
            )
            cards = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"]

        joined_titles = " / ".join(card["title"] for card in cards)
        joined_questions = " / ".join(question for card in cards for question in card["review_questions"])
        self.assertTrue("RAG 准确率优化" in joined_titles or "RAG" in joined_titles)
        self.assertIn("检查检索召回", joined_titles)
        self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", card["title"]) for card in cards))
        self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", card["summary"]) for card in cards))
        self.assertTrue(any("RAG" in card["tags"] for card in cards))
        self.assertIn("你能", joined_questions)

    def test_sqlite_readiness_blocks_low_quality_atom_fragments(self) -> None:
        skeleton = build_course_skeleton(
            title="Fragment course",
            source_url="https://www.bilibili.com/video/BV00000001",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "Fragment lecture",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::seg::00001",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=3.0,
                        text="那第一个视频当中",
                    )
                ],
            )
            store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "# Fragment\n\nOnly a transition fragment.",
                note_id="generated_note_fragment",
                now="2026-05-14T00:03:00Z",
            )
            store._replace_knowledge_cards(
                skeleton.course.course_id,
                [
                    {
                        "card_id": "card_fragment",
                        "course_id": skeleton.course.course_id,
                        "lecture_id": lecture.lecture_id,
                        "title": "那第一个视频当中",
                        "body": "核心意思：那第一个视频当中。",
                        "source_segment_ids": [f"{lecture.lecture_id}::seg::00001"],
                        "tags": [],
                        "atom_type": "concept",
                        "summary": "那第一个视频当中",
                        "review_questions": ["你能解释这个知识点吗？"],
                        "anchor_refs": ["anc_fragment"],
                        "confidence": 0.78,
                        "status_lite": "locked",
                    }
                ],
            )
            readiness = store.summarize_import_readiness(skeleton.course.course_id)

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["ready_lecture_count"], 0)
        self.assertEqual(readiness["total_atom_count"], 0)
        self.assertGreaterEqual(readiness["lectures"][0]["low_quality_atom_count"], 1)
        self.assertIn("atom_quality", readiness["lectures"][0]["missing"])

    def test_sqlite_knowledge_cards_migrate_lite_atom_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "course2knowledge-lite.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE courses (
                    course_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    import_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE lectures (
                    lecture_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    duration_seconds INTEGER,
                    read_status TEXT NOT NULL
                );
                CREATE TABLE knowledge_cards (
                    card_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    lecture_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source_segment_ids_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL
                );
                INSERT INTO courses VALUES ('course_old', 'Old course', '', '', 'completed', '2026-05-14T00:00:00Z', '2026-05-14T00:00:00Z');
                INSERT INTO lectures VALUES ('lecture_old', 'course_old', 'Old lecture', '', '', 1, NULL, 'not_started');
                INSERT INTO knowledge_cards VALUES ('card_old', 'course_old', 'lecture_old', 'RAG evidence', 'RAG retrieves evidence.', '["seg_old"]', '["RAG","evidence"]');
                """
            )
            conn.close()

            store = SQLiteCourseStore(db_path)
            card = store.read_knowledge_card("course_old", "card_old")

        self.assertEqual(card["atom_type"], "concept")
        self.assertEqual(card["summary"], "RAG retrieves evidence.")
        self.assertEqual(card["review_questions"], [])
        self.assertEqual(card["anchor_refs"], [])
        self.assertEqual(card["status_lite"], "locked")

    def test_visual_evidence_is_course_bound_and_queryable(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            card = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"][0]
            path = store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence; Agent plans tool use around that evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            all_visuals = store.list_visual_evidence(course_id=skeleton.course.course_id)
            query_visuals = store.list_visual_evidence(course_id=skeleton.course.course_id, query="tool use")
            selected = store.select_visual_evidence(course_id=skeleton.course.course_id, query="rag")

        self.assertTrue(path.endswith("visual_evidence.json"))
        self.assertEqual(len(all_visuals), 1)
        self.assertEqual(query_visuals[0]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(selected["segment_id"], segment_id)
        self.assertEqual(selected["card_id"], card["card_id"])
        self.assertFalse(Path(selected["image_path"]).is_absolute())

    def test_visual_evidence_rejects_naked_absolute_image_paths(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            with self.assertRaisesRegex(ValueError, "repo-local relative path"):
                store.write_visual_evidence_records(
                    skeleton.course.course_id,
                    [
                        {
                            "visual_id": "visual_bad",
                            "course_id": skeleton.course.course_id,
                            "lecture_id": lecture.lecture_id,
                            "title": "Bad image",
                            "explanation": "This should be blocked.",
                            "image_path": "C:/private/image.png",
                            "provenance": "bad path",
                            "created_at": "2026-05-15T00:00:00Z",
                        }
                    ],
                )

    def test_public_visual_evidence_asset_paths_exist_without_runtime_store(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture = skeleton.lectures[0]
        records = [
            {
                "visual_id": "visual_rag_agent_flow",
                "course_id": skeleton.course.course_id,
                "lecture_id": lecture.lecture_id,
                "title": "RAG and Agent flow",
                "explanation": "RAG grounds answers in retrieved evidence; Agent plans tool use around that evidence.",
                "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
                "provenance": "public demo diagram derived from transcript segment",
                "created_at": "2026-05-15T00:00:00Z",
            },
            {
                "visual_id": "visual_rag_quality_loop",
                "course_id": skeleton.course.course_id,
                "lecture_id": lecture.lecture_id,
                "title": "RAG quality loop",
                "explanation": "Retrieval quality is checked before answer generation.",
                "image_path": "docs/assets/visual-evidence/rag-quality-loop.png",
                "provenance": "public demo diagram derived from transcript segment",
                "created_at": "2026-05-15T00:01:00Z",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_visual_evidence_records(skeleton.course.course_id, records)
            visuals = store.list_visual_evidence(course_id=skeleton.course.course_id)
            selected = store.select_visual_evidence(course_id=skeleton.course.course_id, query="Agent")

        self.assertGreaterEqual(len(visuals), 2)
        self.assertEqual(selected["visual_id"], "visual_rag_agent_flow")
        for item in visuals:
            image_path = str(item["image_path"])
            self.assertFalse(Path(image_path).is_absolute())
            self.assertNotIn("..", Path(image_path).parts)
            self.assertTrue((ROOT / image_path).exists(), image_path)

    def test_reading_progress_rejects_unknown_status(self) -> None:
        skeleton = build_course_skeleton(
            title="AI interview course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "RAG and Agent",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            with self.assertRaisesRegex(ValueError, "status must be one of"):
                store.set_reading_progress(skeleton.course.course_id, skeleton.lectures[0].lecture_id, "mastered")


if __name__ == "__main__":
    unittest.main()
