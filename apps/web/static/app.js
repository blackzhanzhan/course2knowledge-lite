const state = {
  courses: [],
  lectures: [],
  courseId: "",
  lectureSequence: 1,
  lectureId: "",
  coverage: null,
  guideMode: "continue",
  activeView: "courses",
  chatThreadId: "",
  chatBusy: false,
};

const els = {
  status: document.querySelector("#status"),
  viewTitle: document.querySelector("#view-title"),
  viewSubtitle: document.querySelector("#view-subtitle"),
  viewEyebrow: document.querySelector("#view-eyebrow"),
  navItems: document.querySelectorAll(".nav-item"),
  viewPanels: document.querySelectorAll("[data-view-panel]"),
  courseList: document.querySelector("#course-list"),
  coveragePanel: document.querySelector("#coverage-panel"),
  selectedCourseSummary: document.querySelector("#selected-course-summary"),
  lectureAdminList: document.querySelector("#lecture-admin-list"),
  metricCourseCount: document.querySelector("#metric-course-count"),
  metricLectureCount: document.querySelector("#metric-lecture-count"),
  metricCoverage: document.querySelector("#metric-coverage"),
  metricSegments: document.querySelector("#metric-segments"),
  stripStore: document.querySelector("#strip-store"),
  stripAuthority: document.querySelector("#strip-authority"),
  stripGuide: document.querySelector("#strip-guide"),
  stripFrontdesk: document.querySelector("#strip-frontdesk"),
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
  chatInput: document.querySelector("#chat-input"),
  chatLog: document.querySelector("#chat-log"),
  chatSendButton: document.querySelector("#chat-send-button"),
  noteInput: document.querySelector("#note-input"),
  notesList: document.querySelector("#notes-list"),
  bookmarksList: document.querySelector("#bookmarks-list"),
  importButton: document.querySelector("#import-button"),
  refreshButton: document.querySelector("#refresh-button"),
  searchButton: document.querySelector("#search-button"),
  qaButton: document.querySelector("#qa-button"),
  noteButton: document.querySelector("#note-button"),
  cardsButton: document.querySelector("#cards-button"),
  viewJumpButtons: document.querySelectorAll("[data-view-jump]"),
};

const viewCopy = {
  courses: {
    eyebrow: "Web Lite",
    title: "课程管理",
    subtitle: "导入合集，检查课时和转写覆盖，再进入学习交互。",
  },
  study: {
    eyebrow: "Evidence workspace",
    title: "学习交互",
    subtitle: "阅读转写、运行导学、检索片段，并基于引用进行课程问答。",
  },
  cards: {
    eyebrow: "Knowledge workspace",
    title: "知识管理",
    subtitle: "把转写证据整理成卡片、笔记和书签。",
  },
  frontdesk: {
    eyebrow: "Dual frontdesk",
    title: "飞书前台",
    subtitle: "Hermes Lite 读取同一个公开课程 store，不另起私有门户。",
  },
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
  els.status.textContent = statusCopy[text] || text;
}

const statusCopy = {
  "Guide ready / continue": "导学就绪 / 继续学习",
  "Guide ready / walkthrough": "导学就绪 / 讲解导读",
  "Guide ready / self_check": "导学就绪 / 自测",
  "Guide ready / recap": "导学就绪 / 复盘",
  "Reading local course store": "读取本地课程库",
  "No courses": "暂无课程",
  "Import needs a URL": "需要合集链接",
  "Importing Bilibili collection": "正在导入合集",
  "Import accepted": "导入已接受",
  "Import failed": "导入失败",
  "Opening lecture reader": "打开课时阅读",
  "Reader ready / no transcript": "阅读器就绪 / 暂无转写",
  "Building guide": "生成导学",
  "Knowledge cards generated": "知识卡片已生成",
  "Chat needs a course": "先选择一门课程",
  "Chat needs a message": "输入一条消息",
  "Chat is running": "正在对话",
  "Chat ready": "对话就绪",
  "Chat failed": "对话失败",
  "Write a note first": "先写一条笔记",
  "Note saved": "笔记已保存",
  "Bookmark saved": "书签已保存",
  "Load failed": "加载失败",
};

const progressCopy = {
  not_started: "未开始",
  reading: "阅读中",
  read: "已读",
};

function setView(view) {
  const nextView = viewCopy[view] ? view : "courses";
  state.activeView = nextView;
  for (const item of els.navItems) {
    item.classList.toggle("is-active", item.dataset.view === nextView);
  }
  for (const panel of els.viewPanels) {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === nextView);
  }
  const copy = viewCopy[nextView];
  els.viewEyebrow.textContent = copy.eyebrow;
  els.viewTitle.textContent = copy.title;
  els.viewSubtitle.textContent = copy.subtitle;
  renderWorkspaceStrip();
}

function guideModeLabel(mode) {
  return {
    continue: "继续学习",
    walkthrough: "讲解导读",
    self_check: "自测",
    recap: "复盘",
  }[mode] || mode;
}

function renderWorkspaceStrip() {
  const course = selectedCourse();
  const courseCount = state.courses.length;
  const lectureCount = state.lectures.length || Number(course?.lecture_count || 0);
  const courseLabel = course ? course.title || course.course_id : "Public child repo";
  els.stripStore.textContent = courseCount
    ? `${courseCount} courses / ${lectureCount} lectures`
    : "Local course store";
  els.stripAuthority.textContent = courseLabel;
  els.stripGuide.textContent = `${guideModeLabel(state.guideMode)} / read-only`;
  els.stripFrontdesk.textContent = state.activeView === "frontdesk" ? "Hermes Lite active" : "Web + Hermes Lite";
}

async function loadCourses() {
  setStatus("Reading local course store");
  const payload = await getJson("/api/courses");
  state.courses = payload.courses || [];
  renderWorkspaceStrip();
  renderCourseMetrics();
  renderCourses();
  if (state.courses.length) {
    const nextCourseId = state.courseId || state.courses[0].course_id;
    await selectCourse(nextCourseId);
  } else {
    els.segments.innerHTML = '<div class="empty">本地课程库暂无课程。</div>';
    els.coveragePanel.innerHTML = "";
    els.cardsList.innerHTML = "";
    els.guideOutput.innerHTML = "";
    setStatus("No courses");
    renderWorkspaceStrip();
  }
}

async function importCollection() {
  const sourceUrl = els.importUrl.value.trim();
  if (!sourceUrl) {
    els.importReceipt.textContent = "粘贴一个 Bilibili 合集链接。";
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
      <p class="item-meta">已接受：${escapeHtml(course.title || course.course_id)}</p>
      <p class="citation">${Number(payload.lecture_count || importStatus.total_lectures || 0)} 课时 / ${escapeHtml(
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
  if (!state.courses.length) {
    els.courseList.innerHTML = '<div class="empty">本地课程库暂无课程。</div>';
    renderCourseMetrics();
    renderWorkspaceStrip();
    return;
  }
  els.courseList.innerHTML = state.courses
    .map(
      (course) => `
        <article class="course-item ${course.course_id === state.courseId ? "is-active" : ""}" data-course-id="${escapeHtml(
          course.course_id,
        )}">
          <p class="item-title">${escapeHtml(course.title || course.course_id)}</p>
          <p class="item-meta">${Number(course.lecture_count || 0)} 课时 / ${Number(
            course.lecture_transcript_count || 0,
          )} 有转写</p>
          <p class="citation">${escapeHtml(course.course_id)}</p>
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
  renderCourseMetrics();
  renderWorkspaceStrip();
  const payload = await getJson(`/api/lectures?course_id=${encodeURIComponent(courseId)}`);
  state.lectures = payload.lectures || [];
  await loadCoverage();
  renderCourseMetrics();
  renderWorkspaceStrip();
  renderSelectedCourseSummary();
  renderLectureAdminList();
  state.lectureSequence = Number(state.lectures[0]?.sequence || 1);
  renderLectureSelect();
  await loadReader();
  await loadLearningState();
  await loadGuide("continue");
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
    els.coveragePanel.innerHTML = '<div class="empty">转写覆盖信息不可用。</div>';
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
    <p class="item-meta">${covered}/${total} 课时有转写 / ${Number(
      coverage.total_segment_count || 0,
    )} 个片段</p>
  `;
  renderCourseMetrics();
}

function selectedCourse() {
  return state.courses.find((course) => course.course_id === state.courseId) || null;
}

function renderCourseMetrics() {
  const courseCount = state.courses.length;
  const lectureCount = state.lectures.length || Number(selectedCourse()?.lecture_count || 0);
  const coverage = state.coverage || {};
  const percent = Math.round(Number(coverage.coverage_ratio || 0) * 100);
  els.metricCourseCount.textContent = String(courseCount);
  els.metricLectureCount.textContent = String(lectureCount);
  els.metricCoverage.textContent = `${Math.max(0, Math.min(percent, 100))}%`;
  els.metricSegments.textContent = String(Number(coverage.total_segment_count || 0));
  renderWorkspaceStrip();
}

function renderSelectedCourseSummary() {
  const course = selectedCourse();
  if (!course) {
    els.selectedCourseSummary.innerHTML = '<div class="empty">选择一门课程查看详情。</div>';
    return;
  }
  const coverage = state.coverage || {};
  els.selectedCourseSummary.innerHTML = `
    <div class="summary-line">
      <span>课程名称</span>
      <strong>${escapeHtml(course.title || course.course_id)}</strong>
    </div>
    <div class="summary-line">
      <span>来源</span>
      <strong>${escapeHtml(course.source_url || "local store")}</strong>
    </div>
    <div class="summary-line">
      <span>课时状态</span>
      <strong>${Number(course.lecture_transcript_count || 0)} / ${Number(course.lecture_count || 0)} 有转写</strong>
    </div>
    <div class="summary-line">
      <span>证据片段</span>
      <strong>${Number(coverage.total_segment_count || 0)}</strong>
    </div>
  `;
}

function renderLectureAdminList() {
  if (!state.lectures.length) {
    els.lectureAdminList.innerHTML = '<div class="empty">还没有加载课时。</div>';
    return;
  }
  els.lectureAdminList.innerHTML = state.lectures
    .map(
      (lecture) => `
        <button class="lecture-row ${Number(lecture.sequence) === Number(state.lectureSequence) ? "is-active" : ""}"
          type="button"
          data-sequence="${escapeHtml(lecture.sequence)}">
          <span>${escapeHtml(lecture.sequence)}. ${escapeHtml(lecture.title || lecture.lecture_id)}</span>
          <small>${escapeHtml(lecture.bvid || lecture.source_url || lecture.lecture_id)}</small>
        </button>
      `,
    )
    .join("");
  for (const button of els.lectureAdminList.querySelectorAll(".lecture-row")) {
    button.addEventListener("click", async () => {
      state.lectureSequence = Number(button.dataset.sequence || 1);
      renderLectureSelect();
      renderLectureAdminList();
      await loadReader();
      await loadLearningState();
      await loadGuide(state.guideMode === "continue" ? "walkthrough" : state.guideMode);
      setView("study");
    });
  }
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
  els.courseMeta.textContent = `${payload.course?.title || state.courseId} / 第 ${lecture.sequence || ""} 课`;
  els.lectureTitle.textContent = lecture.title || "课时阅读";
  renderLectureAdminList();
  if (!payload.has_transcript) {
    els.segments.innerHTML = '<div class="empty">当前课时还没有转写片段。</div>';
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
            )}" title="收藏片段">收藏</button>
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
  setStatus(`阅读器就绪 / ${payload.segment_count} 个片段`);
}

async function loadGuide(mode = state.guideMode) {
  if (!state.courseId) {
    return;
  }
  state.guideMode = mode || "continue";
  els.guideMode.value = state.guideMode;
  renderWorkspaceStrip();
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
  renderWorkspaceStrip();
  setStatus(`导学就绪 / ${guideModeLabel(state.guideMode)}`);
}

function renderGuide(payload) {
  if (!payload || payload.status === "blocked") {
    els.guideOutput.innerHTML = `
      <div class="empty">
        <p class="blocked">${escapeHtml(payload?.message || "导学暂不可用。")}</p>
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
          <p class="item-title">下一节建议：${escapeHtml(lecture.sequence)} / ${escapeHtml(lecture.title)}</p>
          <p class="item-meta">${escapeHtml(recommendation.reason || "")}</p>
        </div>
        <button class="ghost-button" type="button" id="open-guide-lecture" data-sequence="${escapeHtml(
          lecture.sequence,
        )}">打开</button>
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
            <p class="item-title">下一节阅读目标：${escapeHtml(recap.next_reading_target.sequence)} / ${escapeHtml(
              recap.next_reading_target.title,
            )}</p>
            <p class="item-meta">这是基于转写顺序的阅读建议，不是学习计划。</p>
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
            <p class="citation">第 ${escapeHtml(citation.lecture_sequence)} 课 / ${escapeHtml(
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
            <p class="citation">卡片 / ${escapeHtml(card.card_id)}</p>
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
            <p class="citation">视觉证据 / ${escapeHtml(visual.visual_id)} / ${escapeHtml(visual.image_path)}</p>
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
    <p class="citation">只读 / 不建计划: ${String(!limits.creates_study_plan)} / 不评分: ${String(
      !limits.scores_learner,
    )} / 不建复习队列: ${String(!limits.spaced_review_queue)}</p>
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
    els.cardsList.innerHTML = '<div class="empty">当前课时还没有知识卡片。</div>';
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
            )}" title="收藏卡片">收藏</button>
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
    els.notesList.innerHTML = '<div class="empty">当前课时还没有笔记。</div>';
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
    els.bookmarksList.innerHTML = '<div class="empty">还没有书签。</div>';
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
  setStatus(`阅读状态：${progressCopy[status] || status}`);
}

async function runSearch() {
  if (!state.courseId) {
    return;
  }
  const query = els.searchInput.value.trim();
  if (!query) {
    els.searchResults.innerHTML = '<div class="empty">输入要检索的关键词。</div>';
    return;
  }
  const payload = await getJson(
    `/api/search?course_id=${encodeURIComponent(state.courseId)}&query=${encodeURIComponent(query)}&limit=8`,
  );
  if (!payload.result_count) {
    els.searchResults.innerHTML = '<div class="empty">没有匹配的转写片段。</div>';
    return;
  }
  els.searchResults.innerHTML = payload.results
    .map((result) => {
      const citation = result.citation || {};
      return `
        <article class="result">
          <p class="citation">第 ${escapeHtml(citation.lecture_sequence)} 课 / ${escapeHtml(
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
    els.qaAnswer.innerHTML = '<div class="empty">输入一个问题。</div>';
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
            `<p class="citation">第 ${escapeHtml(citation.lecture_sequence)} 课 / ${escapeHtml(
              citation.segment_id,
            )} / ${secondsLabel(citation.start_seconds)}</p>`,
        )
        .join("")}
    </article>
  `;
}

async function runChat() {
  if (!state.courseId || state.chatBusy) {
    setStatus("Chat needs a course");
    return;
  }
  const message = els.chatInput.value.trim();
  if (!message) {
    setStatus("Chat needs a message");
    return;
  }
  state.chatBusy = true;
  els.chatSendButton.disabled = true;
  appendChatBubble("user", message);
  const assistantBubble = appendChatBubble("assistant", "");
  const eventsWrap = assistantBubble.querySelector(".chat-events");
  const bodyWrap = assistantBubble.querySelector(".chat-body");
  setStatus("Chat is running");
  try {
    const events = await postSse("/api/chat/stream", {
      course_id: state.courseId,
      message,
      thread_id: state.chatThreadId,
      channel: "web",
    });
    renderChatEvents(events, { bodyWrap, eventsWrap });
    const threadState = events.find((event) => event.event === "thread_state")?.data || {};
    state.chatThreadId = threadState.thread?.thread_id || state.chatThreadId;
    setStatus("Chat ready");
  } catch (error) {
    bodyWrap.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
    setStatus("Chat failed");
  } finally {
    state.chatBusy = false;
    els.chatSendButton.disabled = false;
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }
}

async function postSse(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return parseSse(text);
}

function parseSse(text) {
  return text
    .trim()
    .split("\n\n")
    .filter(Boolean)
    .map((block) => {
      const event = { event: "message", id: "", data: {} };
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          event.event = line.slice(7);
        } else if (line.startsWith("id: ")) {
          event.id = line.slice(4);
        } else if (line.startsWith("data: ")) {
          dataLines.push(line.slice(6));
        }
      }
      event.data = JSON.parse(dataLines.join("\n") || "{}");
      return event;
    });
}

function appendChatBubble(role, text) {
  if (!els.chatLog.querySelector(".chat-message")) {
    els.chatLog.innerHTML = "";
  }
  const bubble = document.createElement("article");
  bubble.className = `chat-message is-${role}`;
  bubble.innerHTML = `
    <p class="chat-role">${role === "user" ? "You" : "Hermes Lite"}</p>
    <div class="chat-body">${escapeHtml(text)}</div>
    <div class="chat-events"></div>
  `;
  els.chatLog.appendChild(bubble);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
  return bubble;
}

function renderChatEvents(events, { bodyWrap, eventsWrap }) {
  const messageEvent = events.find((event) => event.event === "message_delta");
  const errorEvent = events.find((event) => event.event === "error");
  const mediaEvents = events.filter((event) => event.event === "media");
  if (messageEvent?.data?.payload?.delta) {
    bodyWrap.innerHTML = `<p>${escapeHtml(messageEvent.data.payload.delta)}</p>`;
  } else if (errorEvent?.data?.payload?.message) {
    bodyWrap.innerHTML = `<p class="blocked">${escapeHtml(errorEvent.data.payload.message)}</p>`;
  } else {
    bodyWrap.innerHTML = '<p class="blocked">No local evidence matched this request.</p>';
  }
  if (mediaEvents.length) {
    bodyWrap.insertAdjacentHTML(
      "beforeend",
      mediaEvents
        .map((event) => {
          const payload = event.data.payload || {};
          return `
            <figure class="chat-media">
              <img src="/${escapeHtml(payload.image_path || "")}" alt="${escapeHtml(payload.title || "Visual evidence")}" />
              <figcaption>${escapeHtml(payload.title || payload.visual_id || "")}</figcaption>
            </figure>
          `;
        })
        .join(""),
    );
  }
  eventsWrap.innerHTML = events
    .filter((event) => event.event !== "thread_state")
    .map((event) => {
      const payload = event.data.payload || {};
      const label = payload.reason || payload.hit_count || payload.visual_id || payload.status || payload.source || "";
      return `<span class="chat-event is-${escapeHtml(event.event)}">${escapeHtml(event.event)}${
        label ? ` / ${escapeHtml(label)}` : ""
      }</span>`;
    })
    .join("");
}

function renderChatEmptyState() {
  if (!els.chatLog || els.chatLog.querySelector(".chat-message")) {
    return;
  }
  els.chatLog.innerHTML = `
    <div class="empty">
      <p>Ask against the selected local course. Events stream from SQLite-backed Lite Chat Core.</p>
      <p class="citation">Try: What is RAG Agent? / Show visual RAG Agent / show cards</p>
    </div>
  `;
}

els.importButton.addEventListener("click", importCollection);
els.refreshButton.addEventListener("click", loadCourses);
els.searchButton.addEventListener("click", runSearch);
els.qaButton.addEventListener("click", runQa);
els.chatSendButton.addEventListener("click", runChat);
els.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    runChat();
  }
});
els.noteButton.addEventListener("click", saveNote);
els.cardsButton.addEventListener("click", generateCards);
els.guideButton.addEventListener("click", () => loadGuide(els.guideMode.value));
for (const item of els.navItems) {
  item.addEventListener("click", () => setView(item.dataset.view));
}
for (const button of els.viewJumpButtons) {
  button.addEventListener("click", () => setView(button.dataset.viewJump));
}
els.progressSelect.addEventListener("change", setProgress);
els.lectureSelect.addEventListener("change", async () => {
  state.lectureSequence = Number(els.lectureSelect.value || 1);
  renderLectureAdminList();
  await loadReader();
  await loadLearningState();
  await loadGuide(state.guideMode === "continue" ? "walkthrough" : state.guideMode);
});

setView("courses");
renderChatEmptyState();

loadCourses().catch((error) => {
  els.segments.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  setStatus("Load failed");
});
