# Showcase Shot List

This document is the capture contract for the public showcase site. The page
must contain at least 15 real screenshots or evidence captures. The current
public page meets that visual threshold with safe Web/API/store/Hermes evidence.
Real Feishu chat remains a separate safe-capture gap and must not be faked with
mother-project production screenshots.

## Demo Case

- Source: `https://space.bilibili.com/1112988584/lists/7726472?type=season`
- Public store: `data/course-store/courses/course_e4af83f2c407/`
- Current known facts: 30 expanded lectures, 3 transcript-backed lectures, 9
  transcript segments, Web Lite workspace, public Hermes Lite profile skeleton.

## Required Shots

| Shot ID | Surface | What It Must Show | Capture Source | Status |
| --- | --- | --- | --- | --- |
| SHOT-01 | Web Lite | Full Web workspace with course list, reader, search, Q&A, notes, bookmarks | Browser at local Web Lite | Available |
| SHOT-02 | Feishu/Hermes Lite | Safe course Q&A reply through the Lite chat surface | Safe Lite chat capture | Pending |
| SHOT-03 | Dual frontdesk | Web and Hermes evidence both using the same public demo course | Composite from real Web and Hermes smoke captures | Available |
| SHOT-04 | Import boundary | Bilibili collection URL accepted as an import source | CLI/API/import JSON evidence | Available |
| SHOT-05 | Lecture expansion | Ordered lecture list with source identifiers and titles | Web/API/store capture | Available |
| SHOT-06 | Course store | Local course files: course, lectures, segments, cards, notes, bookmarks, progress | File tree or store view | Available |
| SHOT-07 | Transcript segments | Timestamped transcript segments with stable segment IDs | Web reader or JSON evidence | Available |
| SHOT-08 | Reader detail | One transcript-backed lecture opened in the Web reader | Browser at Web Lite | Available |
| SHOT-09 | Search result | Query to cited transcript hits | Browser at Web Lite | Available |
| SHOT-10 | Q&A answer | Answer body with visible source citations | Browser at Web Lite | Available |
| SHOT-11 | Knowledge cards | Cards generated from transcript evidence with source segment IDs | Browser at Web Lite | Available |
| SHOT-12 | Notes | A saved note tied to the course and lecture | Browser at Web Lite | Available |
| SHOT-13 | Bookmarks | A bookmark over a segment or card target | Browser at Web Lite | Available |
| SHOT-14 | Reading progress | Status change persisted and reflected in the workspace | Browser at Web Lite | Available |
| SHOT-15 | Hermes profile smoke | Public profile/plugin smoke proving the Lite tool boundary | CLI/profile smoke output | Available |
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

The showcase is visually ready when at least 15 shot slots are backed by real
evidence captures. The current gallery has 15 available shots: `SHOT-01`,
`SHOT-03` through `SHOT-16`. `SHOT-02` remains pending because a real Feishu chat
capture needs a safe public Lite conversation, not a private production export.
