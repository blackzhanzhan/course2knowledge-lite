---
layout: technical
title: 演示隐私规则
permalink: /demo-privacy/
---
# Demo Privacy And Masking Rules

This document defines what may appear in public demo video assets and what must
be hidden or excluded.

## Safe Sources

Use these sources first:

- public Lite Web app
- public Lite local course store
- public Lite docs and GitHub Pages site
- public Lite CLI output
- public Hermes Lite profile sync and smoke output
- sanitized safe Lite chat capture, if available

## Do Not Publish

Never publish:

- raw footage
- private profile files
- auth files
- cookies or browser storage
- API keys or environment dumps
- personal account names
- private chat names
- production chat screenshots
- production identifiers
- absolute private workspace paths
- private project runtime logs
- personal study-domain labels
- unedited terminal output that may include local machine details

## Masking Rules

Mask or crop before export when any of these appear:

- user names or avatars
- organization names
- browser profile names
- local absolute paths
- terminal prompt user or machine name
- source URLs that are not meant to be part of the public demo
- hidden files or folders
- timestamps that tie the recording to a private live chat

Preferred treatment:

- crop the unsafe region when it is outside the product surface
- blur the unsafe label when the surrounding UI is useful
- replace with a short public caption only when the raw screen is not needed

## Public Feishu/Hermes Rule

Feishu/Hermes Lite may be shown only in one of these forms:

1. A safe Lite chat capture that contains no private account, organization, chat,
   or production identifiers.
2. A public Hermes Lite profile smoke screen.
3. A diagram explaining the frontdesk boundary.

Do not use private production chat screenshots as a substitute for public Lite
chat evidence.

## Raw Footage Handling

Raw footage must stay outside git or under ignored temporary paths.

Recommended local paths:

```text
tmp/demo-video/raw/
tmp/demo-video/work/
```

Only edited public assets may be committed:

```text
docs/assets/demo-video/course2knowledge-lite-demo.webm
docs/assets/demo-video/course2knowledge-lite-demo.mp4
docs/assets/demo-video/poster.png
```

## Review Checklist

Before committing public video assets:

- Scrub the video once at normal speed.
- Inspect at least one frame from every major segment.
- Confirm subtitles/captions do not mention private project details.
- Confirm terminal captures do not show secrets or local account names.
- Confirm the public demo still explains the product without private context.
- Confirm the exported video and poster are the only committed media assets.

## Acceptance

The demo is publishable only when a reviewer can watch it without learning
anything about private workspaces, private accounts, private logs, or personal
study data.
