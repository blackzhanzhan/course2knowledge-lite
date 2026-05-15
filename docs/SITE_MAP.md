# Static Site Map

Course2Knowledge Lite uses `docs/` as the GitHub Pages source. The site is a
public product showcase and a technical dossier entry, not the Web Lite runtime
itself.

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
   - Primary evidence slots: Web overview and Feishu/Hermes Q&A.

2. **Walkthrough**
   - Six-step flow: import collection, expand lectures, capture evidence, build
     course store, read on Web, ask from Feishu.
   - This section explains the runtime sequence before individual screenshots.

3. **Frontdesks**
   - Web Lite: deep reading, search, annotation, citation inspection.
   - Feishu/Hermes Lite: ask, lookup, status, citation-based Q&A in chat.
   - The section must not present Feishu as a footnote or optional afterthought.

4. **Module Evidence Plan**
   - At least 15 real screenshots or evidence captures are required before the
     case is visually convincing.
   - The current page defines 16 shot slots, each with a stable `SHOT-*` ID.
   - Pending slots must remain visibly pending until real evidence is captured.
   - Detailed capture contract: [`SHOWCASE_SHOT_LIST.md`](SHOWCASE_SHOT_LIST.md).

5. **Product Thought**
   - Express the core idea: course videos are not lacking content; the content is
     trapped in the timeline.
   - Lite turns the timeline into evidence, evidence into a course store, and the
     store into two user-facing entry points.

6. **Public Boundary**
   - Included: Bilibili import, transcript evidence, course store, Web Lite,
     Feishu/Hermes Lite, citation Q&A, notes, bookmarks, progress.
   - Removed: planning layer, feedback layer, exercise review, learner scoring,
     private orchestration, production identifiers, private logs.
   - The public version is a deliberately trimmed loop, not a thin demo.

7. **Technical Dossier**
   - Product boundary: [`PRODUCT_BOUNDARY.md`](PRODUCT_BOUNDARY.md)
   - Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
   - Data model: [`DATA_MODEL.md`](DATA_MODEL.md)
   - Bilibili import: [`BILIBILI_IMPORT.md`](BILIBILI_IMPORT.md)
   - Web Lite: [`WEB_LITE.md`](WEB_LITE.md)
   - Feishu Lite: [`FEISHU_LITE.md`](FEISHU_LITE.md)
   - Testing: [`TESTING.md`](TESTING.md)
   - Deployment: [`DEPLOYMENT.md`](DEPLOYMENT.md)

8. **Deploy**
   - Minimal local install path.
   - Web Lite command.
   - Optional public Hermes profile sync and smoke command.

## Current Showcase Assets

- `docs/assets/showcase/web-lite-real-course-desktop.png`
- `docs/assets/showcase/web-lite-real-course-mobile.png`

These images were captured from the local public Lite Web workspace at
`http://127.0.0.1:3027/` against the public demo course store. They count as
available evidence for `SHOT-01` and `SHOT-16`.

## GitHub Pages Setup

Recommended GitHub Pages setting:

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

No build step is required.
