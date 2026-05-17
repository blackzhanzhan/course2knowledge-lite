const state = {
  courses: [],
  lectures: [],
  courseId: "",
  lectureSequence: 1,
  lectureId: "",
  coverage: null,
  activeView: "interaction",
  chatThreadId: "",
  chatBusy: false,
  cards: [],
  courseCards: [],
  transientAtomSignals: new Set(),
  currentProgressStatus: "not_started",
};

const els = {
  status: document.querySelector("#status"),
  viewTitle: document.querySelector("#view-title"),
  viewSubtitle: document.querySelector("#view-subtitle"),
  viewEyebrow: document.querySelector("#view-eyebrow"),
  navItems: document.querySelectorAll(".nav-item"),
  viewPanels: document.querySelectorAll("[data-view-panel]"),
  courseSelect: document.querySelector("#course-select"),
  notesCourseSelect: document.querySelector("#notes-course-select"),
  lectureSelect: document.querySelector("#lecture-select"),
  notesLectureSelect: document.querySelector("#notes-lecture-select"),
  courseList: document.querySelector("#course-list"),
  coveragePanel: document.querySelector("#coverage-panel"),
  selectedCourseSummary: document.querySelector("#selected-course-summary"),
  lectureAdminList: document.querySelector("#lecture-admin-list"),
  importUrl: document.querySelector("#import-url"),
  importReceipt: document.querySelector("#import-receipt"),
  courseMeta: document.querySelector("#course-meta"),
  lectureTitle: document.querySelector("#lecture-title"),
  progressSelect: document.querySelector("#progress-select"),
  segments: document.querySelector("#segments"),
  cardsList: document.querySelector("#cards-list"),
  chatInput: document.querySelector("#chat-input"),
  chatLog: document.querySelector("#chat-log"),
  chatSendButton: document.querySelector("#chat-send-button"),
  atomProgressSummary: document.querySelector("#atom-progress-summary"),
  atomStateList: document.querySelector("#atom-state-list"),
  markdownNotes: document.querySelector("#markdown-notes"),
  noteInput: document.querySelector("#note-input"),
  notesList: document.querySelector("#notes-list"),
  bookmarksList: document.querySelector("#bookmarks-list"),
  importButton: document.querySelector("#import-button"),
  refreshButton: document.querySelector("#refresh-button"),
  noteButton: document.querySelector("#note-button"),
  cardsButton: document.querySelector("#cards-button"),
  viewJumpButtons: document.querySelectorAll("[data-view-jump]"),
};

const viewCopy = {
  interaction: {
    eyebrow: "Interaction",
    title: "互动",
    subtitle: "选择课程和课时后，直接在这里和学习助手聊天，右侧同步看知识节点状态。",
  },
  courses: {
    eyebrow: "Courses",
    title: "课程管理",
    subtitle: "导入课程、查看课时、删除课程，并直观看到课程内部的知识原子节点。",
  },
  notes: {
    eyebrow: "Notes",
    title: "课程笔记",
    subtitle: "显示真实 Markdown / Obsidian 内容；未接入时只展示本地笔记和课程证据。",
  },
};

const statusCopy = {
  "Reading local course store": "读取本地课程库",
  "No courses": "暂无课程",
  "Import needs a URL": "需要合集链接",
  "Importing Bilibili collection": "正在导入合集",
  "Import accepted": "导入已接收",
  "Import failed": "导入失败",
  "Course deleted": "课程已删除",
  "Delete failed": "删除失败",
  "Opening lecture reader": "打开课时证据",
  "Reader ready / no transcript": "证据就绪 / 暂无转写",
  "Knowledge cards generated": "知识节点已生成",
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

const atomStateCopy = {
  new: "待提问",
  appeared: "已出现",
  read: "已读课时",
};

const progressCopy = {
  not_started: "未开始",
  reading: "阅读中",
  read: "已读",
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
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (payload !== undefined) {
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || `Request failed: ${response.status}`);
  }
  return result;
}

function setStatus(text) {
  els.status.textContent = statusCopy[text] || text;
}

function selectedCourse() {
  return state.courses.find((course) => course.course_id === state.courseId) || null;
}

function selectedLecture() {
  return (
    state.lectures.find((lecture) => Number(lecture.sequence) === Number(state.lectureSequence)) ||
    state.lectures[0] ||
    null
  );
}

function setView(view) {
  const nextView = viewCopy[view] ? view : "interaction";
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
}

function clearCourseSurface() {
  state.lectures = [];
  state.courseId = "";
  state.lectureId = "";
  state.cards = [];
  state.courseCards = [];
  els.courseSelect.innerHTML = '<option value="">暂无课程</option>';
  els.notesCourseSelect.innerHTML = '<option value="">暂无课程</option>';
  els.lectureSelect.innerHTML = '<option value="">暂无课时</option>';
  els.notesLectureSelect.innerHTML = '<option value="">暂无课时</option>';
  els.courseList.innerHTML = '<div class="empty">本地课程库暂无课程。</div>';
  els.coveragePanel.innerHTML = "";
  els.selectedCourseSummary.innerHTML = "";
  els.lectureAdminList.innerHTML = "";
  els.cardsList.innerHTML = '<div class="empty">暂无课程，暂时没有知识原子。</div>';
  els.segments.innerHTML = '<div class="empty">导入课程后，这里会显示当前课时证据。</div>';
  els.notesList.innerHTML = '<div class="empty">暂无课程笔记。</div>';
  els.bookmarksList.innerHTML = "";
  els.courseMeta.textContent = "尚未选择课程";
  els.lectureTitle.textContent = "等待课程";
  renderMarkdownUnavailable();
  renderAtomStates();
}

async function loadCourses() {
  setStatus("Reading local course store");
  const payload = await getJson("/api/courses");
  state.courses = payload.courses || [];
  if (!state.courses.length) {
    clearCourseSurface();
    setStatus("No courses");
    return;
  }
  const nextCourseId =
    state.courseId && state.courses.some((course) => course.course_id === state.courseId)
      ? state.courseId
      : state.courses[0].course_id;
  renderCourseSelects();
  renderCourses();
  await selectCourse(nextCourseId);
}

function renderCourseSelects() {
  const options = state.courses
    .map((course) => `<option value="${escapeHtml(course.course_id)}">${escapeHtml(course.title || course.course_id)}</option>`)
    .join("");
  els.courseSelect.innerHTML = options || '<option value="">暂无课程</option>';
  els.notesCourseSelect.innerHTML = options || '<option value="">暂无课程</option>';
  els.courseSelect.value = state.courseId;
  els.notesCourseSelect.value = state.courseId;
}

function renderLectureSelects() {
  const options = state.lectures
    .map(
      (lecture) =>
        `<option value="${escapeHtml(lecture.sequence)}">${escapeHtml(lecture.sequence)} / ${escapeHtml(
          lecture.title || lecture.lecture_id,
        )}</option>`,
    )
    .join("");
  els.lectureSelect.innerHTML = options || '<option value="">暂无课时</option>';
  els.notesLectureSelect.innerHTML = options || '<option value="">暂无课时</option>';
  els.lectureSelect.value = String(state.lectureSequence);
  els.notesLectureSelect.value = String(state.lectureSequence);
}

async function selectCourse(courseId) {
  if (!courseId) {
    clearCourseSurface();
    return;
  }
  state.courseId = courseId;
  state.transientAtomSignals.clear();
  state.cards = [];
  state.courseCards = [];
  renderCourseSelects();
  renderCourses();
  renderAtomStates();
  const payload = await getJson(`/api/lectures?course_id=${encodeURIComponent(courseId)}`);
  state.lectures = payload.lectures || [];
  state.lectureSequence = Number(state.lectures[0]?.sequence || 1);
  renderLectureSelects();
  await loadCoverage();
  renderSelectedCourseSummary();
  renderLectureAdminList();
  await loadCourseCards();
  await loadReader();
  await loadLearningState();
}

async function selectLecture(sequence) {
  const parsed = Number(sequence || 1);
  state.lectureSequence = Number.isFinite(parsed) ? parsed : 1;
  state.transientAtomSignals.clear();
  renderLectureSelects();
  renderLectureAdminList();
  await loadReader();
  await loadLearningState();
}

async function importCollection() {
  const sourceUrl = els.importUrl.value.trim();
  if (!sourceUrl) {
    els.importReceipt.textContent = "粘贴一个 Bilibili 合集链接。";
    setStatus("Import needs a URL");
    return;
  }
  els.importButton.disabled = true;
  els.importReceipt.textContent = "正在导入课程元数据...";
  setStatus("Importing Bilibili collection");
  try {
    const payload = await sendJson("/api/import", { source_url: sourceUrl });
    const course = payload.course || {};
    const importStatus = payload.import_status || {};
    els.importReceipt.innerHTML = `
      <p class="item-meta">已接收：${escapeHtml(course.title || course.course_id)}</p>
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
    return;
  }
  els.courseList.innerHTML = state.courses
    .map(
      (course) => `
        <article class="course-item ${course.course_id === state.courseId ? "is-active" : ""}" data-course-id="${escapeHtml(
          course.course_id,
        )}">
          <div>
            <p class="item-title">${escapeHtml(course.title || course.course_id)}</p>
            <p class="item-meta">${Number(course.lecture_count || 0)} 课时 / ${Number(
              course.lecture_transcript_count || 0,
            )} 有转写</p>
            <p class="citation">${escapeHtml(course.course_id)}</p>
          </div>
          <button class="ghost-button delete-course-button" type="button" data-course-id="${escapeHtml(
            course.course_id,
          )}" title="删除课程">删除</button>
        </article>
      `,
    )
    .join("");
  for (const item of els.courseList.querySelectorAll(".course-item")) {
    item.addEventListener("click", () => selectCourse(item.dataset.courseId));
  }
  for (const button of els.courseList.querySelectorAll(".delete-course-button")) {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteCourse(button.dataset.courseId);
    });
  }
}

async function deleteCourse(courseId) {
  const course = state.courses.find((item) => item.course_id === courseId);
  if (!courseId || !window.confirm(`删除课程「${course?.title || courseId}」？本地 SQLite 中的课时、笔记、知识节点也会一起删除。`)) {
    return;
  }
  try {
    await sendJson(`/api/courses?course_id=${encodeURIComponent(courseId)}`, undefined, { method: "DELETE" });
    if (state.courseId === courseId) {
      state.courseId = "";
    }
    await loadCourses();
    setStatus("Course deleted");
  } catch (error) {
    setStatus("Delete failed");
    els.importReceipt.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
  }
}

async function loadCoverage() {
  if (!state.courseId) {
    return;
  }
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
    <p class="item-meta">${covered}/${total} 课时有转写 / ${Number(coverage.total_segment_count || 0)} 个片段</p>
  `;
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
      <span>知识原子</span>
      <strong>${Number(state.courseCards.length || 0)}</strong>
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
      await selectLecture(button.dataset.sequence);
      setView("interaction");
    });
  }
}

async function loadReader() {
  if (!state.courseId || !state.lectures.length) {
    return;
  }
  setStatus("Opening lecture reader");
  const payload = await getJson(
    `/api/reader?course_id=${encodeURIComponent(state.courseId)}&lecture_sequence=${encodeURIComponent(
      state.lectureSequence,
    )}`,
  );
  const lecture = payload.lecture || {};
  if (state.lectureId && state.lectureId !== lecture.lecture_id) {
    state.transientAtomSignals.clear();
  }
  state.lectureId = lecture.lecture_id || "";
  els.courseMeta.textContent = `${payload.course?.title || state.courseId} / 第 ${lecture.sequence || ""} 课`;
  els.lectureTitle.textContent = lecture.title || "课时证据";
  if (!payload.has_transcript) {
    els.segments.innerHTML = '<div class="empty">当前课时还没有转写片段。</div>';
    await loadCards();
    renderMarkdownUnavailable();
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
  renderMarkdownUnavailable();
  setStatus(`证据就绪 / ${payload.segment_count} 个片段`);
}

async function loadLearningState() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const lectureQuery = `course_id=${encodeURIComponent(state.courseId)}&lecture_id=${encodeURIComponent(state.lectureId)}`;
  const [notesPayload, bookmarksPayload, progressPayload] = await Promise.all([
    getJson(`/api/notes?${lectureQuery}`),
    getJson(`/api/bookmarks?course_id=${encodeURIComponent(state.courseId)}`),
    getJson(`/api/progress?${lectureQuery}`),
  ]);
  renderNotes(notesPayload.notes || []);
  renderBookmarks(bookmarksPayload.bookmarks || []);
  const progress = (progressPayload.progress || [])[0] || {};
  state.currentProgressStatus = progress.status || "not_started";
  els.progressSelect.value = state.currentProgressStatus;
  renderAtomStates();
}

async function loadCards() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  const payload = await getJson(
    `/api/cards?course_id=${encodeURIComponent(state.courseId)}&lecture_id=${encodeURIComponent(state.lectureId)}`,
  );
  state.cards = payload.cards || [];
  renderAtomStates();
}

async function loadCourseCards() {
  if (!state.courseId) {
    return;
  }
  const payload = await getJson(`/api/cards?course_id=${encodeURIComponent(state.courseId)}`);
  state.courseCards = payload.cards || [];
  renderCourseCards();
  renderSelectedCourseSummary();
}

function renderCourseCards() {
  if (!state.courseCards.length) {
    els.cardsList.innerHTML = '<div class="empty">当前课程还没有知识原子。进入互动模块后，可从当前课时生成。</div>';
    return;
  }
  els.cardsList.innerHTML = state.courseCards
    .map(
      (card) => `
        <article class="knowledge-card">
          <div class="segment-head">
            <p class="segment-title">${escapeHtml(card.title || card.card_id)}</p>
            <button class="ghost-button bookmark-card" type="button" data-card-id="${escapeHtml(
              card.card_id,
            )}" title="收藏知识原子">收藏</button>
          </div>
          <p>${escapeHtml(card.body)}</p>
          <p class="citation">${escapeHtml(card.lecture_id)} / ${escapeHtml((card.source_segment_ids || []).join(", "))}</p>
          <p class="tags">${(card.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</p>
        </article>
      `,
    )
    .join("");
  for (const button of els.cardsList.querySelectorAll(".bookmark-card")) {
    button.addEventListener("click", () => createBookmark("card", button.dataset.cardId));
  }
}

function atomStateForCard(card) {
  if (state.currentProgressStatus === "read") {
    return "read";
  }
  if (state.transientAtomSignals.has(card.card_id)) {
    return "appeared";
  }
  return "new";
}

function renderAtomStates() {
  const cards = state.cards || [];
  if (!cards.length) {
    els.atomProgressSummary.textContent = "当前课时暂无知识节点";
    els.atomStateList.innerHTML = '<div class="empty">生成知识节点后，这里会显示本节候选知识点。</div>';
    return;
  }
  const counts = cards.reduce(
    (result, card) => {
      result[atomStateForCard(card)] += 1;
      return result;
    },
    { new: 0, appeared: 0, read: 0 },
  );
  const activeCount = counts.read || counts.appeared;
  els.atomProgressSummary.textContent = `${activeCount}/${cards.length} 个已有课堂信号`;
  els.atomStateList.innerHTML = cards
    .map((card) => {
      const atomState = atomStateForCard(card);
      return `
        <article class="atom-item is-${atomState}">
          <div>
            <p class="atom-title">${escapeHtml(card.title || card.card_id)}</p>
            <p class="citation">${escapeHtml((card.tags || []).slice(0, 3).join(" / ") || card.card_id)}</p>
          </div>
          <span class="atom-state">${atomStateCopy[atomState]}</span>
        </article>
      `;
    })
    .join("");
}

function markAtomsFromText(text) {
  const content = String(text || "").toLowerCase();
  if (!content || !state.cards.length) {
    return;
  }
  for (const card of state.cards) {
    const candidates = [card.title, ...(card.tags || [])]
      .map((value) => String(value || "").trim().toLowerCase())
      .filter((value) => value.length >= 3);
    if (candidates.some((value) => content.includes(value))) {
      state.transientAtomSignals.add(card.card_id);
    }
  }
  renderAtomStates();
}

async function generateCards() {
  if (!state.courseId || !state.lectureId) {
    return;
  }
  await sendJson("/api/cards/generate", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    overwrite: true,
  });
  await loadCards();
  await loadCourseCards();
  setStatus("Knowledge cards generated");
}

function renderMarkdownUnavailable() {
  const course = selectedCourse();
  const lecture = selectedLecture();
  els.markdownNotes.innerHTML = `
    <article class="markdown-empty">
      <p class="item-title">Markdown / Obsidian 内容未接入或未生成</p>
      <p class="item-meta">${escapeHtml(course?.title || "暂无课程")} ${
        lecture ? `/ 第 ${escapeHtml(lecture.sequence)} 课 ${escapeHtml(lecture.title || "")}` : ""
      }</p>
      <p>当前本地库里没有真实的课程 Markdown 文件。下面只显示 SQLite 中已经保存的本地笔记、书签和当前课时证据。</p>
    </article>
  `;
}

function renderNotes(notes) {
  renderMarkdownUnavailable();
  if (!notes.length) {
    els.notesList.innerHTML = '<div class="empty">当前课时还没有本地笔记。</div>';
    return;
  }
  els.notesList.innerHTML = `
    <h3>本地笔记</h3>
    ${notes
      .map(
        (note) => `
          <article class="result">
            <p>${escapeHtml(note.body)}</p>
            <p class="citation">${escapeHtml(note.updated_at || note.created_at)} / ${escapeHtml(note.note_id)}</p>
          </article>
        `,
      )
      .join("")}
  `;
}

function renderBookmarks(bookmarks) {
  if (!bookmarks.length) {
    els.bookmarksList.innerHTML = '<div class="empty">还没有书签。</div>';
    return;
  }
  els.bookmarksList.innerHTML = `
    <h3>书签</h3>
    ${bookmarks
      .map(
        (bookmark) => `
          <article class="result">
            <p>${escapeHtml(bookmark.target_type)}: ${escapeHtml(bookmark.target_id)}</p>
            <p class="citation">${escapeHtml(bookmark.created_at)} / ${escapeHtml(bookmark.bookmark_id)}</p>
          </article>
        `,
      )
      .join("")}
  `;
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
  state.currentProgressStatus = status;
  renderAtomStates();
  await sendJson("/api/progress", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    status,
  });
  state.currentProgressStatus = status;
  renderAtomStates();
  setStatus(`阅读状态：${progressCopy[status] || status}`);
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
    <p class="chat-role">${role === "user" ? "我" : "学习助手"}</p>
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
    markAtomsFromText(messageEvent.data.payload.delta);
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
      <p>这里可以直接围绕当前课程提问。回答来自本地 SQLite 课程库和 Lite Chat Core。</p>
      <p class="citation">试试：What is RAG Agent? / Show visual RAG Agent / show cards</p>
    </div>
  `;
}

els.importButton.addEventListener("click", importCollection);
els.refreshButton.addEventListener("click", loadCourses);
els.chatSendButton.addEventListener("click", runChat);
els.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    runChat();
  }
});
els.noteButton.addEventListener("click", saveNote);
els.cardsButton.addEventListener("click", generateCards);
for (const item of els.navItems) {
  item.addEventListener("click", () => setView(item.dataset.view));
}
for (const button of els.viewJumpButtons) {
  button.addEventListener("click", () => setView(button.dataset.viewJump));
}
els.progressSelect.addEventListener("change", setProgress);
els.courseSelect.addEventListener("change", () => selectCourse(els.courseSelect.value));
els.notesCourseSelect.addEventListener("change", () => selectCourse(els.notesCourseSelect.value));
els.lectureSelect.addEventListener("change", () => selectLecture(els.lectureSelect.value));
els.notesLectureSelect.addEventListener("change", () => selectLecture(els.notesLectureSelect.value));

setView("interaction");
renderChatEmptyState();
renderMarkdownUnavailable();

loadCourses().catch((error) => {
  els.segments.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  setStatus("Load failed");
});
