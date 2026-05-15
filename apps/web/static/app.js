const state = {
  courses: [],
  lectures: [],
  courseId: "",
  lectureSequence: 1,
  lectureId: "",
  coverage: null,
  guideMode: "continue",
};

const els = {
  status: document.querySelector("#status"),
  courseList: document.querySelector("#course-list"),
  coveragePanel: document.querySelector("#coverage-panel"),
  importUrl: document.querySelector("#import-url"),
  importReceipt: document.querySelector("#import-receipt"),
  courseMeta: document.querySelector("#course-meta"),
  lectureTitle: document.querySelector("#lecture-title"),
  lectureSelect: document.querySelector("#lecture-select"),
  progressSelect: document.querySelector("#progress-select"),
  guideMode: document.querySelector("#guide-mode"),
  guideButton: document.querySelector("#guide-button"),
  guideOutput: document.querySelector("#guide-output"),
  segments: document.querySelector("#segments"),
  cardsList: document.querySelector("#cards-list"),
  searchInput: document.querySelector("#search-input"),
  searchResults: document.querySelector("#search-results"),
  qaInput: document.querySelector("#qa-input"),
  qaAnswer: document.querySelector("#qa-answer"),
  noteInput: document.querySelector("#note-input"),
  notesList: document.querySelector("#notes-list"),
  bookmarksList: document.querySelector("#bookmarks-list"),
  importButton: document.querySelector("#import-button"),
  refreshButton: document.querySelector("#refresh-button"),
  searchButton: document.querySelector("#search-button"),
  qaButton: document.querySelector("#qa-button"),
  noteButton: document.querySelector("#note-button"),
  cardsButton: document.querySelector("#cards-button"),
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
    els.coveragePanel.innerHTML = "";
    els.cardsList.innerHTML = "";
    els.guideOutput.innerHTML = "";
    setStatus("No courses");
  }
}

async function importCollection() {
  const sourceUrl = els.importUrl.value.trim();
  if (!sourceUrl) {
    els.importReceipt.textContent = "Paste a Bilibili collection URL.";
    setStatus("Import needs a URL");
    return;
  }
  els.importButton.disabled = true;
  els.importReceipt.textContent = "Importing collection metadata...";
  setStatus("Importing Bilibili collection");
  try {
    const payload = await sendJson("/api/import", { source_url: sourceUrl });
    const course = payload.course || {};
    const importStatus = payload.import_status || {};
    els.importReceipt.innerHTML = `
      <p class="item-meta">Accepted ${escapeHtml(course.title || course.course_id)}</p>
      <p class="citation">${Number(payload.lecture_count || importStatus.total_lectures || 0)} lectures / ${escapeHtml(
        importStatus.stage || "collection_expanded",
      )}</p>
    `;
    state.courseId = course.course_id || state.courseId;
    await loadCourses();
    if (course.course_id) {
      await selectCourse(course.course_id);
    }
    setStatus("Import accepted");
  } catch (error) {
    els.importReceipt.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
    setStatus("Import failed");
  } finally {
    els.importButton.disabled = false;
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
  await loadCoverage();
  state.lectureSequence = Number(state.lectures[0]?.sequence || 1);
  renderLectureSelect();
  await loadReader();
  await loadLearningState();
  await loadGuide("continue");
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

async function loadCoverage() {
  const payload = await getJson(`/api/coverage?course_id=${encodeURIComponent(state.courseId)}`);
  state.coverage = payload.coverage || null;
  renderCoverage();
}

function renderCoverage() {
  const coverage = state.coverage;
  if (!coverage) {
    els.coveragePanel.innerHTML = '<div class="empty">Coverage unavailable.</div>';
    return;
  }
  const percent = Math.round(Number(coverage.coverage_ratio || 0) * 100);
  const clampedPercent = Math.max(0, Math.min(percent, 100));
  const covered = Number(coverage.covered_lecture_count || 0);
  const total = Number(coverage.lecture_count || 0);
  els.coveragePanel.innerHTML = `
    <div class="coverage-meter" aria-label="Transcript coverage">
      <div class="coverage-bar" style="width: ${clampedPercent}%"></div>
    </div>
    <p class="item-meta">${covered}/${total} lectures with transcripts / ${Number(
      coverage.total_segment_count || 0,
    )} segments</p>
  `;
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
    await loadCards();
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
  await loadCards();
  setStatus(`Reader ready / ${payload.segment_count} segments`);
}

async function loadGuide(mode = state.guideMode) {
  if (!state.courseId) {
    return;
  }
  state.guideMode = mode || "continue";
  els.guideMode.value = state.guideMode;
  const params = new URLSearchParams({
    course_id: state.courseId,
    mode: state.guideMode,
    limit: "4",
  });
  if (state.guideMode !== "continue" && state.lectureId) {
    params.set("lecture_id", state.lectureId);
  }
  setStatus("Building guide");
  const payload = await getJson(`/api/guide?${params.toString()}`);
  renderGuide(payload);
  setStatus(`Guide ready / ${state.guideMode}`);
}

function renderGuide(payload) {
  if (!payload || payload.status === "blocked") {
    els.guideOutput.innerHTML = `
      <div class="empty">
        <p class="blocked">${escapeHtml(payload?.message || "Guide unavailable.")}</p>
        <p class="citation">${escapeHtml(payload?.reason || "blocked")}</p>
      </div>
    `;
    return;
  }
  if (payload.mode === "continue") {
    renderContinueGuide(payload);
  } else if (payload.mode === "walkthrough") {
    renderWalkthroughGuide(payload);
  } else if (payload.mode === "self_check") {
    renderSelfCheckGuide(payload);
  } else {
    renderRecapGuide(payload);
  }
}

function renderContinueGuide(payload) {
  const lecture = payload.lecture || {};
  const recommendation = payload.recommendation || {};
  const preview = payload.preview || {};
  els.guideOutput.innerHTML = `
    <article class="guide-block">
      <div class="segment-head">
        <div>
          <p class="item-title">Next useful lecture: ${escapeHtml(lecture.sequence)} / ${escapeHtml(lecture.title)}</p>
          <p class="item-meta">${escapeHtml(recommendation.reason || "")}</p>
        </div>
        <button class="ghost-button" type="button" id="open-guide-lecture" data-sequence="${escapeHtml(
          lecture.sequence,
        )}">Open</button>
      </div>
      ${renderCitations(preview.segments || [])}
      ${renderGuideCards(preview.cards || [])}
      ${renderVisualEvidence(preview.visual_evidence || [])}
      ${renderGuideLimits(payload)}
    </article>
  `;
  const openButton = document.querySelector("#open-guide-lecture");
  openButton?.addEventListener("click", async () => {
    state.lectureSequence = Number(openButton.dataset.sequence || 1);
    renderLectureSelect();
    await loadReader();
    await loadLearningState();
    await loadGuide("walkthrough");
  });
}

function renderWalkthroughGuide(payload) {
  els.guideOutput.innerHTML = `
    ${(payload.walkthrough || [])
      .map(
        (step) => `
          <article class="guide-block">
            <p class="item-title">${escapeHtml(step.title || step.step_id)}</p>
            <p>${escapeHtml(step.body || "")}</p>
            ${renderCitations(step.citations || [])}
            ${renderGuideCards(step.cards || [])}
            ${renderVisualEvidence(step.visual_evidence || [])}
          </article>
        `,
      )
      .join("")}
    ${renderGuideLimits(payload)}
  `;
}

function renderSelfCheckGuide(payload) {
  els.guideOutput.innerHTML = `
    ${(payload.questions || [])
      .map(
        (question) => `
          <article class="guide-block">
            <p class="item-title">${escapeHtml(question.prompt || question.question_id)}</p>
            <p class="item-meta">${escapeHtml(question.answer_policy || "")}</p>
            ${renderCitations(question.citations || [])}
          </article>
        `,
      )
      .join("")}
    ${renderGuideLimits(payload)}
  `;
}

function renderRecapGuide(payload) {
  const recap = payload.recap || {};
  els.guideOutput.innerHTML = `
    ${(recap.key_points || [])
      .map(
        (point) => `
          <article class="guide-block">
            <p class="item-title">${escapeHtml(point.title || "Key point")}</p>
            <p>${escapeHtml(point.body || "")}</p>
            <p class="citation">${escapeHtml((point.source_segment_ids || []).join(", "))}</p>
          </article>
        `,
      )
      .join("")}
    ${
      recap.next_reading_target?.lecture_id
        ? `<article class="guide-block">
            <p class="item-title">Next reading target: ${escapeHtml(recap.next_reading_target.sequence)} / ${escapeHtml(
              recap.next_reading_target.title,
            )}</p>
            <p class="item-meta">A suggestion from transcript-backed lecture order, not a schedule.</p>
          </article>`
        : ""
    }
    ${renderVisualEvidence(recap.visual_evidence || [])}
    ${renderGuideLimits(payload)}
  `;
}

function renderCitations(citations) {
  if (!citations.length) {
    return "";
  }
  return `
    <div class="guide-evidence">
      ${citations
        .map(
          (citation) => `
            <p class="citation">Lecture ${escapeHtml(citation.lecture_sequence)} / ${escapeHtml(
              citation.segment_id,
            )} / ${secondsLabel(citation.start_seconds)}</p>
            <p>${escapeHtml(citation.text || "")}</p>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderGuideCards(cards) {
  if (!cards.length) {
    return "";
  }
  return `
    <div class="guide-evidence">
      ${cards
        .map(
          (card) => `
            <p class="citation">Card / ${escapeHtml(card.card_id)}</p>
            <p>${escapeHtml(card.title || "")}</p>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderVisualEvidence(visuals) {
  if (!visuals.length) {
    return "";
  }
  return `
    <div class="guide-evidence">
      ${visuals
        .map(
          (visual) => `
            <p class="citation">Visual / ${escapeHtml(visual.visual_id)} / ${escapeHtml(visual.image_path)}</p>
            <p>${escapeHtml(visual.title || "")}: ${escapeHtml(visual.explanation || "")}</p>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderGuideLimits(payload) {
  const limits = payload.limits || {};
  return `
    <p class="citation">Read-only / no plan: ${String(!limits.creates_study_plan)} / no scoring: ${String(
      !limits.scores_learner,
    )} / no review queue: ${String(!limits.spaced_review_queue)}</p>
  `;
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

async function loadCards() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const payload = await getJson(
    `/api/cards?course_id=${encodeURIComponent(state.courseId)}&lecture_id=${encodeURIComponent(state.lectureId)}`,
  );
  renderCards(payload.cards || []);
}

function renderCards(cards) {
  if (!cards.length) {
    els.cardsList.innerHTML = '<div class="empty">No knowledge cards for this lecture yet.</div>';
    return;
  }
  els.cardsList.innerHTML = cards
    .map(
      (card) => `
        <article class="knowledge-card">
          <div class="segment-head">
            <p class="segment-title">${escapeHtml(card.title || card.card_id)}</p>
            <button class="ghost-button bookmark-card" type="button" data-card-id="${escapeHtml(
              card.card_id,
            )}" title="Bookmark card">Bookmark</button>
          </div>
          <p>${escapeHtml(card.body)}</p>
          <p class="citation">${escapeHtml((card.source_segment_ids || []).join(", "))}</p>
          <p class="tags">${(card.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</p>
        </article>
      `,
    )
    .join("");
  for (const button of els.cardsList.querySelectorAll(".bookmark-card")) {
    button.addEventListener("click", () => createBookmark("card", button.dataset.cardId));
  }
}

async function generateCards() {
  if (!state.courseId) {
    return;
  }
  await sendJson("/api/cards/generate", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    overwrite: true,
  });
  await loadCards();
  setStatus("Knowledge cards generated");
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

els.importButton.addEventListener("click", importCollection);
els.refreshButton.addEventListener("click", loadCourses);
els.searchButton.addEventListener("click", runSearch);
els.qaButton.addEventListener("click", runQa);
els.noteButton.addEventListener("click", saveNote);
els.cardsButton.addEventListener("click", generateCards);
els.guideButton.addEventListener("click", () => loadGuide(els.guideMode.value));
els.progressSelect.addEventListener("change", setProgress);
els.lectureSelect.addEventListener("change", async () => {
  state.lectureSequence = Number(els.lectureSelect.value || 1);
  await loadReader();
  await loadLearningState();
  await loadGuide(state.guideMode === "continue" ? "walkthrough" : state.guideMode);
});

loadCourses().catch((error) => {
  els.segments.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  setStatus("Load failed");
});
