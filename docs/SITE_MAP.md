# Static Site Map

Course2Knowledge Lite uses `docs/` as the GitHub Pages source. The site is a
public product showcase, not the Web Lite runtime itself.

## Homepage Sections

1. **Hero**
   - Product name: Course2Knowledge Lite.
   - One-line promise: turn online course videos into an interactive knowledge
     base.
   - First visual signal: a real Web Lite workspace screenshot from a local
     Bilibili collection import.

2. **Effect Showcase**
   - Real screenshots from the public Lite app.
   - Desktop workspace view.
   - Mobile responsive view.
   - Case metrics: 30 lectures, 3 transcript-backed lectures, 9 transcript
     segments, citation Q&A, cards, notes, bookmarks, and reading progress.

3. **Real Case Walkthrough**
   - Source: a Bilibili collection URL.
   - Result: course skeleton, lecture list, transcript segments, knowledge
     cards, search, Q&A, and local reading state.
   - Evidence posture: screenshots and facts come from the public local store.

4. **Architecture And Ideas**
   - The course timeline becomes a local knowledge store.
   - Transcript segments are the evidence layer.
   - Cards, search, Q&A, notes, bookmarks, and progress are projections over
     that evidence.
   - Web Lite and Feishu/Hermes Lite are user surfaces over the same store.

5. **Product Boundary**
   - Public capabilities are listed honestly.
   - Removed private loops are listed plainly.
   - The Lite project is positioned as a course knowledge workspace, not a
     closed-loop learning coach.

6. **Deploy In Minutes**
   - Install locally with Python packaging.
   - Start Web Lite from the CLI.
   - Sync the public Hermes profile when Feishu/Hermes Lite is needed.

7. **Repository Links**
   - README.
   - Architecture.
   - Product boundary.
   - Deployment.
   - Web Lite.
   - Feishu Lite.

## Showcase Assets

- `docs/assets/showcase/web-lite-real-course-desktop.png`
- `docs/assets/showcase/web-lite-real-course-mobile.png`

These images were captured from the local public Lite Web workspace at
`http://127.0.0.1:3027/` against the public demo course store.

## GitHub Pages Setup

Recommended GitHub Pages setting:

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

No build step is required.
