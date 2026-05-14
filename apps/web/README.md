# Web Lite App

Public Web workspace for course library, reading, search, Q&A, notes,
bookmarks, and lightweight progress.

Current slice:

- `server.py` runs a small local Web Lite workspace with only Python stdlib.
- The first screen opens the local course library, lecture reader, transcript
  search, and citation Q&A.
- The API reads `data/course-store` through public package APIs only.

Run:

```bash
python apps/web/server.py --port 3014
```

Package-style run:

```bash
course2knowledge-lite web
```
