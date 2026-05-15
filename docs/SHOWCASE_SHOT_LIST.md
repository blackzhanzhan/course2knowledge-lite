# Showcase Shot List

This document is the capture contract for the public showcase site. The page
should eventually contain at least 15 real screenshots or evidence captures.
Pending slots in `docs/index.html` are not product proof until the corresponding
real run is captured and checked in.

## Demo Case

- Source: `https://space.bilibili.com/1112988584/lists/7726472?type=season`
- Public store: `data/course-store/courses/course_e4af83f2c407/`
- Current known facts: 30 expanded lectures, 3 transcript-backed lectures, 9
  transcript segments, Web Lite workspace, public Hermes Lite profile skeleton.

## Required Shots

| Shot ID | Surface | What It Must Show | Capture Source | Status |
| --- | --- | --- | --- | --- |
| SHOT-01 | Web Lite | Full Web workspace with course list, reader, search, Q&A, notes, bookmarks | Browser at local Web Lite | Available |
| SHOT-02 | Feishu/Hermes Lite | Safe course Q&A reply through the Lite chat surface | Feishu/Hermes Lite smoke or safe chat | Pending |
| SHOT-03 | Dual frontdesk | Web and Feishu both using the same public demo course | Composite from two real captures | Pending |
| SHOT-04 | Import boundary | Bilibili collection URL accepted as an import source | CLI/API/import JSON evidence | Pending |
| SHOT-05 | Lecture expansion | Ordered lecture list with source identifiers and titles | Web/API/store capture | Pending |
| SHOT-06 | Course store | Local course files: course, lectures, segments, cards, notes, bookmarks, progress | File tree or store view | Pending |
| SHOT-07 | Transcript segments | Timestamped transcript segments with stable segment IDs | Web reader or JSON evidence | Pending |
| SHOT-08 | Reader detail | One transcript-backed lecture opened in the Web reader | Browser at Web Lite | Pending |
| SHOT-09 | Search result | Query to cited transcript hits | Browser at Web Lite | Pending |
| SHOT-10 | Q&A answer | Answer body with visible source citations | Browser at Web Lite | Pending |
| SHOT-11 | Knowledge cards | Cards generated from transcript evidence with source segment IDs | Browser at Web Lite | Pending |
| SHOT-12 | Notes | A saved note tied to the course and lecture | Browser at Web Lite | Pending |
| SHOT-13 | Bookmarks | A bookmark over a segment or card target | Browser at Web Lite | Pending |
| SHOT-14 | Reading progress | Status change persisted and reflected in the workspace | Browser at Web Lite | Pending |
| SHOT-15 | Hermes profile smoke | Public profile/plugin smoke proving the Lite tool boundary | CLI/profile smoke output | Pending |
| SHOT-16 | Mobile Web | Responsive mobile view of the same public store | Browser mobile viewport | Available |

## Capture Rules

- Do not use mother-project private chats, production identifiers, or private
  Learning OS runtime files.
- Do not replace a pending slot with a mock image.
- Keep private tokens, cookies, account identifiers, and local secrets out of all
  screenshots.
- Prefer the public Lite app, public Lite CLI, public Hermes profile skeleton,
  and local public demo store as evidence sources.
- If a shot requires Feishu, capture only a safe Lite conversation or a sanitized
  smoke surface that does not expose private user or organization data.

## Acceptance

The showcase is considered visually convincing only after at least 15 shot slots
are backed by real evidence captures. Until then, the site is a designed
technical dossier with explicit pending evidence targets.
