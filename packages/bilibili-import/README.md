# Bilibili Import Package

Boundary for public Bilibili course import.

Current slice:

- Expand a Bilibili collection URL into ordered video references.
- Return `sequence`, `bvid`, `title`, and canonical video URL.
- Hand the expanded collection to the local course store as a course skeleton.
- Fetch one lecture's available Bilibili subtitles as transcript segments.
- Leave subtitle extraction, multimodal processing, compilation, and store writes
  beyond the initial skeleton to later import stages.

Authenticated Bilibili subtitles may require `BILIBILI_COOKIE` in the local
environment. Do not commit cookie material.
