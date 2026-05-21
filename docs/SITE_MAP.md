---
layout: technical
title: 站点地图
permalink: /site-map/
---
# Static Site Map

Course2Knowledge Lite uses `docs/` as the GitHub Pages source. The site is a
public product showcase and a technical dossier entry, not the Web Lite runtime
itself. The page defaults to Chinese and provides a same-page English toggle.

## Homepage Responsibility

The homepage must satisfy two audiences:

- Reviewers and interviewers should understand the project in three minutes.
- Developers should know where to inspect architecture, data, tests, and
  deployment in ten minutes.

The main product idea is:

```text
Bilibili Collection
  -> Transcript Evidence
  -> Course Knowledge Store
  -> Web Lite + Feishu/Hermes Lite
```

The Web frontdesk is the inspectable workspace. The Feishu/Hermes frontdesk is
the conversational workspace. Both consume the same public course store.

## Homepage Sections

1. **System**
   - Product name: Course2Knowledge Lite.
   - Promise: turn a course timeline into a readable, searchable, askable
     knowledge base.
   - First-viewport structure: Bilibili collection, transcript evidence, course
     store, Web Lite, and Feishu/Hermes Lite.
   - Primary evidence slots: Web overview and dual-frontdesk boundary proof.

2. **Demo Video**
   - Embed the public short demo video after the system section.
   - Show the same case chain as the screenshot gallery: import receipt,
     lecture expansion, transcript segments, Web reader/search/Q&A, cards, and
     Hermes Lite boundary proof.
   - Link directly to `/course2knowledge-lite/demo-video/` and `/course2knowledge-lite/demo-privacy/` so the showcase
     keeps its technical-dossier responsibility.

3. **Walkthrough**
   - Six-step flow: import collection, expand lectures, capture evidence, build
     course store, read on Web, ask from Feishu.
   - This section explains the runtime sequence before individual screenshots.

4. **Frontdesks**
   - Web Lite: deep reading, search, annotation, citation inspection.
   - Feishu/Hermes Lite: ask, lookup, status, citation-based Q&A in chat.
   - The section must not present Feishu as a footnote or optional afterthought.

5. **Module Evidence Plan**
   - The current page includes 16 real screenshots or evidence captures.
   - The shot set keeps stable `SHOT-*` IDs.
   - `SHOT-02` remains a future safe Feishu chat capture; it is not shown with a
     private production substitute.
   - Detailed capture contract: [`/course2knowledge-lite/showcase-shot-list/`](/course2knowledge-lite/showcase-shot-list/).

6. **Product Thought**
   - Express the core idea: course videos are not lacking content; the content is
     trapped in the timeline.
   - Lite turns the timeline into evidence, evidence into a course store, and the
     store into two user-facing entry points.

7. **Public Boundary**
   - Included: Bilibili import, transcript evidence, course store, Web Lite,
     Feishu/Hermes Lite, citation Q&A, notes, bookmarks, progress.
   - Removed: planning layer, feedback layer, exercise review, learner scoring,
     private orchestration, production identifiers, private logs.
   - The public version is a deliberately trimmed loop, not a thin demo.

8. **Technical Dossier**
   - Demo video: [`/course2knowledge-lite/demo-video/`](/course2knowledge-lite/demo-video/)
   - Privacy and masking rules: [`/course2knowledge-lite/demo-privacy/`](/course2knowledge-lite/demo-privacy/)
   - Product boundary: [`/course2knowledge-lite/product-boundary/`](/course2knowledge-lite/product-boundary/)
   - Architecture: [`/course2knowledge-lite/architecture/`](/course2knowledge-lite/architecture/)
   - Data model: [`/course2knowledge-lite/data-model/`](/course2knowledge-lite/data-model/)
   - Bilibili import: [`/course2knowledge-lite/bilibili-import/`](/course2knowledge-lite/bilibili-import/)
   - Web Lite: [`/course2knowledge-lite/web-lite/`](/course2knowledge-lite/web-lite/)
   - Feishu Lite: [`/course2knowledge-lite/feishu-lite/`](/course2knowledge-lite/feishu-lite/)
   - Testing: [`/course2knowledge-lite/testing/`](/course2knowledge-lite/testing/)
   - Deployment: [`/course2knowledge-lite/deployment/`](/course2knowledge-lite/deployment/)

9. **Deploy**
   - Minimal local install path.
   - Web Lite command.
   - Optional public Hermes profile sync and smoke command.

## Current Showcase Assets

The real demo gallery lives under `docs/assets/demos/`:

- `shot-01-web-overview.png`
- `shot-03-dual-frontdesk.png`
- `shot-04-import-receipt.png`
- `shot-05-lecture-expansion.png`
- `shot-06-course-store-files.png`
- `shot-07-transcript-segments.png`
- `shot-08-reader-detail.png`
- `shot-09-search-result.png`
- `shot-10-qa-answer.png`
- `shot-11-knowledge-cards.png`
- `shot-12-notes.png`
- `shot-13-bookmarks.png`
- `shot-14-reading-progress.png`
- `shot-15-hermes-smoke.png`
- `shot-16-mobile-web.png`
- `docs/assets/visual-evidence/rag-agent-flow.png` as `SHOT-17`

These images were captured from the local public Lite Web workspace at
`http://127.0.0.1:3027/`, local API/store evidence, and public Hermes Lite
profile smoke against the public demo course store. They satisfy the 15-shot
threshold and include a public visual-evidence reply while keeping production
chat captures out of the public repo.

## Demo Video Plan

The public video plan lives in [`/course2knowledge-lite/demo-video/`](/course2knowledge-lite/demo-video/), with masking
rules in [`/course2knowledge-lite/demo-privacy/`](/course2knowledge-lite/demo-privacy/). The short homepage video should
reuse the same public course case as the screenshot gallery: import receipt,
lecture expansion, transcript segments, Web reader/search/Q&A, knowledge cards,
and Hermes Lite boundary proof. Raw footage must stay out of git.

Committed public homepage assets:

- `docs/assets/demo-video/course2knowledge-lite-demo.webm`
- `docs/assets/demo-video/course2knowledge-lite-demo.mp4`
- `docs/assets/demo-video/poster.png`

## GitHub Pages Setup

Recommended GitHub Pages setting:

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

GitHub Pages should use its normal Jekyll rendering pass. Public technical
documents are exposed through route permalinks such as `/architecture/`,
`/bilibili-import/`, `/deployment/`, and `/testing/`. Do not link to raw
Markdown filenames such as `BILIBILI_IMPORT.md` from the public site.
