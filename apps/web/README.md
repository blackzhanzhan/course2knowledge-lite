# Web Lite App

Public Web cockpit for course import, course management, guided reading,
search, Q&A, notes, bookmarks, and lightweight progress.

Current slice:

- `server.py` runs a small local Web Lite workspace with only Python stdlib.
- The first screen opens the local course-management cockpit: import, course
  list, transcript coverage, lecture health, and progress controls.
- Search and citation Q&A live under the learning-interaction view, not as the
  default course-management surface.
- The API reads `data/course-store` through public package APIs only.

Run:

```bash
python apps/web/server.py --port 3014
```

Package-style run:

```bash
course2knowledge-lite web
```
