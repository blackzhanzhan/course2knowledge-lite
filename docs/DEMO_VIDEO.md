# Demo Video Plan

This document defines the public demo video for Course2Knowledge Lite. The video
is a showcase asset and a technical walkthrough map. It must make the product
feel real without exposing private workspaces, private chat surfaces, raw
recordings, or personal study context.

## Public Positioning

Course2Knowledge Lite turns an online course into an interactive knowledge base.

The demo should make this idea visible:

```text
Bilibili Collection
  -> Transcript Evidence
  -> Course Knowledge Store
  -> Web Lite
  -> Feishu/Hermes Lite
```

The product thought:

> Course videos are not short of content. The content is trapped in a timeline.
> Course2Knowledge Lite turns the timeline into evidence, the evidence into a
> course store, and the store into two frontdesks: inspectable Web and
> conversational Feishu/Hermes.

## Short Showcase Video

Target length: 60-100 seconds.

Target placement: the GitHub Pages homepage showcase section.

Format:

- `docs/assets/demo-video/course2knowledge-lite-demo.webm`
- `docs/assets/demo-video/course2knowledge-lite-demo.mp4`
- `docs/assets/demo-video/poster.png`

### 90-Second Storyboard

| Time | Visual | Voice / Caption | Evidence Source |
| --- | --- | --- | --- |
| 0-8s | Product title over Web Lite overview | "Turn a course timeline into an interactive knowledge base." | `SHOT-01` |
| 8-18s | Bilibili collection URL and import receipt | "The input is a real Bilibili collection, not a hand-written fixture." | `SHOT-04` |
| 18-28s | Expanded lecture list | "The importer expands the collection into ordered lectures and source identifiers." | `SHOT-05` |
| 28-40s | Transcript segments with timestamps | "Transcript segments become the first layer of course evidence." | `SHOT-07` |
| 40-52s | Course store files / records | "The course store keeps courses, lectures, segments, cards, notes, bookmarks, and progress." | `SHOT-06` |
| 52-65s | Web reader and search | "Web Lite is the inspectable workspace for reading, search, and citation review." | `SHOT-08`, `SHOT-09` |
| 65-78s | Q&A answer with citations and knowledge cards | "Answers are grounded in visible course evidence, not free-floating chat." | `SHOT-10`, `SHOT-11` |
| 78-88s | Dual-frontdesk and Hermes smoke | "The Feishu/Hermes Lite surface uses the same public course store as the Web workspace." | `SHOT-03`, `SHOT-15` |
| 88-96s | Closing system slice | "One store. Two frontdesks. A course that can be read, searched, and asked." | Site system slice |

### On-Screen Text

Keep on-screen text short and factual:

- Online course -> interactive knowledge base
- Transcript evidence, not vague summaries
- Web Lite for inspection
- Feishu/Hermes Lite for conversation
- One local course store
- Public Lite: no private learning loops

Avoid marketing cliches and inflated claims. The demo should feel like a real
tool that can be inspected.

## Technical Walkthrough Video

Target length: 3-5 minutes.

Target placement: technical dossier section or README link.

### Walkthrough Outline

1. Product boundary
   - Public Lite keeps the course knowledge loop.
   - Private planning, scoring, and feedback loops are not included.

2. Import boundary
   - Bilibili collection URL.
   - Course metadata and lecture expansion.
   - Transcript normalization.

3. Evidence model
   - Timestamped transcript segments.
   - Source-linked knowledge cards.
   - Notes, bookmarks, and reading progress.

4. Web Lite
   - Course library.
   - Lecture reader.
   - Search.
   - Citation Q&A.
   - Knowledge card inspection.

5. Feishu/Hermes Lite
   - Public profile sync and smoke.
   - Chat surface as a second frontdesk over the same store.
   - No private production chat screenshots in the public repo.

6. Deployment
   - `pip install -e .`
   - `course2knowledge-lite web`
   - optional Hermes Lite profile sync and smoke.

## Capture Sequence

Record in this order so the video has one coherent case:

1. Start the public Web Lite app against the existing public demo store.
2. Open the GitHub Pages site locally and capture the system slice.
3. Open Web Lite overview.
4. Show the Bilibili import receipt.
5. Show lecture expansion.
6. Show transcript segments.
7. Show reader detail.
8. Search one course concept.
9. Ask one citation-based question.
10. Show knowledge cards.
11. Show notes, bookmarks, and reading progress.
12. Show Hermes Lite smoke or safe Lite chat capture.
13. End on the system slice.

## Editing Rules

- Keep cuts fast but readable; no step should flash too quickly to inspect.
- Prefer hard cuts or subtle fades; avoid decorative effects.
- Use zoom only when a citation, timestamp, or dual-frontdesk boundary needs
  emphasis.
- Add captions for important transitions instead of long narration.
- Keep the final public video below 25 MB when practical.
- Export both `webm` and `mp4`.

## Acceptance

- The 90-second video can stand alone on the homepage.
- The same public course case appears across all shown modules.
- At least one timestamped transcript segment is visible.
- At least one answer with visible citations is visible.
- The dual-frontdesk idea is explicit.
- No private workspace, private production chat, secret, raw recording, or
  personal study context is visible.
