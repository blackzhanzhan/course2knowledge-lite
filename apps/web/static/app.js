const state = {
  courses: [],
  lectures: [],
  courseId: "",
  lectureSequence: 1,
  lectureId: "",
};

const els = {
  status: document.querySelector("#status"),
  courseList: document.querySelector("#course-list"),
  courseMeta: document.querySelector("#course-meta"),
  lectureTitle: document.querySelector("#lecture-title"),
  lectureSelect: document.querySelector("#lecture-select"),
  progressSelect: document.querySelector("#progress-select"),
  segments: document.querySelector("#segments"),
  searchInput: document.querySelector("#search-input"),
  searchResults: document.querySelector("#search-results"),
  qaInput: document.querySelector("#qa-input"),
  qaAnswer: document.querySelector("#qa-answer"),
  noteInput: document.querySelector("#note-input"),
  notesList: document.querySelector("#notes-list"),
  bookmarksList: document.querySelector("#bookmarks-list"),
  refreshButton: document.querySelector("#refresh-button"),
  searchButton: document.querySelector("#search-button"),
  qaButton: document.querySelector("#qa-button"),
  noteButton: document.querySelector("#note-button"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function secondsLabel(value) {
  const total = Math.max(Number(value || 0), 0);
  const minutes = Math.floor(total / 60);
  const seconds = Math.floor(total % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function sendJson(url, payload, { method = "POST" } = {}) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || `Request failed: ${response.status}`);
  }
  return result;
}

function setStatus(text) {
  els.status.textContent = text;
}

async function loadCourses() {
  setStatus("Reading local course store");
  const payload = await getJson("/api/courses");
  state.courses = payload.courses || [];
  renderCourses();
  if (state.courses.length) {
    const nextCourseId = state.courseId || state.courses[0].course_id;
    await selectCourse(nextCourseId);
  } else {
    els.segments.innerHTML = '<div class="empty">No local courses found.</div>';
    setStatus("No courses");
  }
}

function renderCourses() {
  els.courseList.innerHTML = state.courses
    .map(
      (course) => `
        <article class="course-item ${course.course_id === state.courseId ? "is-active" : ""}" data-course-id="${escapeHtml(
          course.course_id,
        )}">
          <p class="item-title">${escapeHtml(course.title || course.course_id)}</p>
          <p class="item-meta">${Number(course.lecture_count || 0)} lectures / ${Number(
            course.lecture_transcript_count || 0,
          )} with transcripts</p>
        </article>
      `,
    )
    .join("");
  for (const item of els.courseList.querySelectorAll(".course-item")) {
    item.addEventListener("click", () => selectCourse(item.dataset.courseId));
  }
}

async function selectCourse(courseId) {
  state.courseId = courseId;
  renderCourses();
  const payload = await getJson(`/api/lectures?course_id=${encodeURIComponent(courseId)}`);
  state.lectures = payload.lectures || [];
  state.lectureSequence = Number(state.lectures[0]?.sequence || 1);
  renderLectureSelect();
  await loadReader();
  await loadLearningState();
  await runSearch();
  await runQa();
}

function renderLectureSelect() {
  els.lectureSelect.innerHTML = state.lectures
    .map(
      (lecture) =>
        `<option value="${escapeHtml(lecture.sequence)}">${escapeHtml(lecture.sequence)} / ${escapeHtml(
          lecture.title || lecture.lecture_id,
        )}</option>`,
    )
    .join("");
  els.lectureSelect.value = String(state.lectureSequence);
}

async function loadReader() {
  if (!state.courseId) {
    return;
  }
  setStatus("Opening lecture reader");
  const payload = await getJson(
    `/api/reader?course_id=${encodeURIComponent(state.courseId)}&lecture_sequence=${encodeURIComponent(
      state.lectureSequence,
    )}`,
  );
  const lecture = payload.lecture || {};
  state.lectureId = lecture.lecture_id || "";
  els.courseMeta.textContent = `${payload.course?.title || state.courseId} / lecture ${lecture.sequence || ""}`;
  els.lectureTitle.textContent = lecture.title || "Lecture Reader";
  if (!payload.has_transcript) {
    els.segments.innerHTML = '<div class="empty">This lecture has no transcript segments yet.</div>';
    setStatus("Reader ready / no transcript");
    return;
  }
  els.segments.innerHTML = (payload.segments || [])
    .map(
      (segment) => `
        <article class="segment">
          <div class="segment-head">
            <p class="segment-title">${secondsLabel(segment.start_seconds)}-${secondsLabel(segment.end_seconds)}</p>
            <button class="ghost-button bookmark-segment" type="button" data-segment-id="${escapeHtml(
              segment.segment_id,
            )}" title="Bookmark segment">Bookmark</button>
          </div>
          <p>${escapeHtml(segment.text)}</p>
          <p class="citation">${escapeHtml(segment.segment_id)}</p>
        </article>
      `,
    )
    .join("");
  for (const button of els.segments.querySelectorAll(".bookmark-segment")) {
    button.addEventListener("click", () => createBookmark("segment", button.dataset.segmentId));
  }
  setStatus(`Reader ready / ${payload.segment_count} segments`);
}

async function loadLearningState() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const lectureQuery = `course_id=${encodeURIComponent(state.courseId)}&lecture_id=${encodeURIComponent(
    state.lectureId,
  )}`;
  const [notesPayload, bookmarksPayload, progressPayload] = await Promise.all([
    getJson(`/api/notes?${lectureQuery}`),
    getJson(`/api/bookmarks?course_id=${encodeURIComponent(state.courseId)}`),
    getJson(`/api/progress?${lectureQuery}`),
  ]);
  renderNotes(notesPayload.notes || []);
  renderBookmarks(bookmarksPayload.bookmarks || []);
  const progress = (progressPayload.progress || [])[0] || {};
  els.progressSelect.value = progress.status || "not_started";
}

function renderNotes(notes) {
  if (!notes.length) {
    els.notesList.innerHTML = '<div class="empty">No notes for this lecture.</div>';
    return;
  }
  els.notesList.innerHTML = notes
    .map(
      (note) => `
        <article class="result">
          <p>${escapeHtml(note.body)}</p>
          <p class="citation">${escapeHtml(note.updated_at || note.created_at)} / ${escapeHtml(note.note_id)}</p>
        </article>
      `,
    )
    .join("");
}

function renderBookmarks(bookmarks) {
  if (!bookmarks.length) {
    els.bookmarksList.innerHTML = '<div class="empty">No bookmarks yet.</div>';
    return;
  }
  els.bookmarksList.innerHTML = bookmarks
    .map(
      (bookmark) => `
        <article class="result">
          <p>${escapeHtml(bookmark.target_type)}: ${escapeHtml(bookmark.target_id)}</p>
          <p class="citation">${escapeHtml(bookmark.created_at)} / ${escapeHtml(bookmark.bookmark_id)}</p>
        </article>
      `,
    )
    .join("");
}

async function saveNote() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const body = els.noteInput.value.trim();
  if (!body) {
    setStatus("Write a note first");
    return;
  }
  await sendJson("/api/notes", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    body,
  });
  els.noteInput.value = "";
  await loadLearningState();
  setStatus("Note saved");
}

async function createBookmark(targetType, targetId) {
  if (!state.courseId || !targetId) {
    return;
  }
  await sendJson("/api/bookmarks", {
    course_id: state.courseId,
    target_type: targetType,
    target_id: targetId,
  });
  await loadLearningState();
  setStatus("Bookmark saved");
}

async function setProgress() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const status = els.progressSelect.value;
  await sendJson("/api/progress", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    status,
  });
  await loadCourses();
  setStatus(`Progress set to ${status}`);
}

async function runSearch() {
  if (!state.courseId) {
    return;
  }
  const query = els.searchInput.value.trim();
  if (!query) {
    els.searchResults.innerHTML = '<div class="empty">Enter a search query.</div>';
    return;
  }
  const payload = await getJson(
    `/api/search?course_id=${encodeURIComponent(state.courseId)}&query=${encodeURIComponent(query)}&limit=8`,
  );
  if (!payload.result_count) {
    els.searchResults.innerHTML = '<div class="empty">No transcript matches.</div>';
    return;
  }
  els.searchResults.innerHTML = payload.results
    .map((result) => {
      const citation = result.citation || {};
      return `
        <article class="result">
          <p class="citation">Lecture ${escapeHtml(citation.lecture_sequence)} / ${escapeHtml(
            citation.lecture_title,
          )} / ${secondsLabel(citation.start_seconds)}</p>
          <p>${escapeHtml(result.snippet || citation.text)}</p>
        </article>
      `;
    })
    .join("");
}

async function runQa() {
  if (!state.courseId) {
    return;
  }
  const question = els.qaInput.value.trim();
  if (!question) {
    els.qaAnswer.innerHTML = '<div class="empty">Enter a question.</div>';
    return;
  }
  const payload = await getJson(
    `/api/qa?course_id=${encodeURIComponent(state.courseId)}&question=${encodeURIComponent(question)}&limit=5`,
  );
  const citations = payload.citations || [];
  els.qaAnswer.innerHTML = `
    <article class="answer-card">
      <p class="${payload.status === "blocked" ? "blocked" : ""}">${escapeHtml(payload.answer)}</p>
      <p class="citation">${escapeHtml(payload.status)} / ${Number(payload.citation_count || 0)} citations</p>
      ${citations
        .map(
          (citation) =>
            `<p class="citation">Lecture ${escapeHtml(citation.lecture_sequence)} / ${escapeHtml(
              citation.segment_id,
            )} / ${secondsLabel(citation.start_seconds)}</p>`,
        )
        .join("")}
    </article>
  `;
}

els.refreshButton.addEventListener("click", loadCourses);
els.searchButton.addEventListener("click", runSearch);
els.qaButton.addEventListener("click", runQa);
els.noteButton.addEventListener("click", saveNote);
els.progressSelect.addEventListener("change", setProgress);
els.lectureSelect.addEventListener("change", async () => {
  state.lectureSequence = Number(els.lectureSelect.value || 1);
  await loadReader();
  await loadLearningState();
});

loadCourses().catch((error) => {
  els.segments.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  setStatus("Load failed");
});
