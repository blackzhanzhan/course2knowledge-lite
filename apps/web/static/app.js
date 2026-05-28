const state = {
  courses: [],
  lectures: [],
  courseId: "",
  lectureSequence: 1,
  lectureId: "",
  coverage: null,
  readiness: null,
  activeView: "interaction",
  chatThreads: [],
  chatThreadId: "",
  chatBusy: false,
  chatTurnId: 0,
  visitorSessionId: "",
  importPollTimer: null,
  qrLoginId: "",
  qrLoginStatus: "",
  qrLoginImage: "",
  qrLoginPollTimer: null,
  cards: [],
  courseCards: [],
  transientAtomSignals: new Set(),
  currentProgressStatus: "not_started",
  currentHermesAtoms: [],
  publicDemo: false,
  courseStoreLoading: true,
};

const els = {
  status: document.querySelector("#status"),
  viewTitle: document.querySelector("#view-title"),
  viewSubtitle: document.querySelector("#view-subtitle"),
  viewEyebrow: document.querySelector("#view-eyebrow"),
  navItems: document.querySelectorAll(".nav-item"),
  viewPanels: document.querySelectorAll("[data-view-panel]"),
  experienceGuide: document.querySelector("#experience-guide"),
  courseSelect: document.querySelector("#course-select"),
  notesCourseSelect: document.querySelector("#notes-course-select"),
  lectureSelect: document.querySelector("#lecture-select"),
  notesLectureSelect: document.querySelector("#notes-lecture-select"),
  courseList: document.querySelector("#course-list"),
  coveragePanel: document.querySelector("#coverage-panel"),
  selectedCourseSummary: document.querySelector("#selected-course-summary"),
  lectureAdminList: document.querySelector("#lecture-admin-list"),
  importUrl: document.querySelector("#import-url"),
  bilibiliCookie: document.querySelector("#bilibili-cookie"),
  rememberBilibiliCookie: document.querySelector("#remember-bilibili-cookie"),
  bilibiliCookieStatus: document.querySelector("#bilibili-cookie-status"),
  pasteCookieButton: document.querySelector("#paste-cookie-button"),
  qrLoginButton: document.querySelector("#qr-login-button"),
  clearQrLoginButton: document.querySelector("#clear-qr-login-button"),
  qrLoginPanel: document.querySelector("#qr-login-panel"),
  clearCookieButton: document.querySelector("#clear-cookie-button"),
  clearStoredCookieButton: document.querySelector("#clear-stored-cookie-button"),
  importReceipt: document.querySelector("#import-receipt"),
  courseMeta: document.querySelector("#course-meta"),
  lectureTitle: document.querySelector("#lecture-title"),
  progressSelect: document.querySelector("#progress-select"),
  segments: document.querySelector("#segments"),
  cardsList: document.querySelector("#cards-list"),
  chatInput: document.querySelector("#chat-input"),
  chatLog: document.querySelector("#chat-log"),
  chatThreadSelect: document.querySelector("#chat-thread-select"),
  chatSendButton: document.querySelector("#chat-send-button"),
  endSessionButton: document.querySelector("#end-session-button"),
  atomProgressSummary: document.querySelector("#atom-progress-summary"),
  atomStateList: document.querySelector("#atom-state-list"),
  learningSignalList: document.querySelector("#learning-signal-list"),
  lessonAdvancePanel: document.querySelector("#lesson-advance-panel"),
  lessonAdvanceButton: document.querySelector("#lesson-advance-button"),
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
  "Public demo is read-only": "云端体验限制删除、Cookie 和本地写入",
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

const publicDemoPreferredLectureKeywords = ["cache", "高速缓冲存储器"];
const publicDemoLoadingCopy = "正在准备示例课程，约 3-8 秒";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function displaySourceUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "local store";
  }
  try {
    const url = new URL(raw);
    for (const key of [...url.searchParams.keys()]) {
      if (key === "vd_source" || key === "spm_id_from" || key.startsWith("utm_") || key.startsWith("spm")) {
        url.searchParams.delete(key);
      }
    }
    url.hash = "";
    return url.toString();
  } catch {
    return raw.replace(/([?&])(vd_source|spm_id_from|utm_[^=&]+|spm[^=&]*)=[^&]*/gi, "$1").replace(/[?&]$/, "");
  }
}

function publicDemoDefaultLectureSequence(lectures) {
  if (!isPublicDemo() || !Array.isArray(lectures) || !lectures.length) {
    return Number(lectures?.[0]?.sequence || 1);
  }
  const preferred = lectures.find((lecture) => {
    const title = String(lecture.title || "").toLowerCase();
    return publicDemoPreferredLectureKeywords.some((keyword) => title.includes(keyword.toLowerCase()));
  });
  return Number(preferred?.sequence || lectures[0]?.sequence || 1);
}

function secondsLabel(value) {
  const total = Math.max(Number(value || 0), 0);
  const minutes = Math.floor(total / 60);
  const seconds = Math.floor(total % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function ensureVisitorSessionId() {
  if (state.visitorSessionId) {
    return state.visitorSessionId;
  }
  const storageKey = "course2knowledge_lite_visitor_session_id";
  const existing = window.sessionStorage?.getItem(storageKey) || "";
  if (existing) {
    state.visitorSessionId = existing;
    return existing;
  }
  const randomPart =
    window.crypto?.randomUUID?.().replaceAll("-", "") ||
    `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
  state.visitorSessionId = `v_${randomPart.slice(0, 32)}`;
  window.sessionStorage?.setItem(storageKey, state.visitorSessionId);
  return state.visitorSessionId;
}

function resetVisitorSessionId() {
  const storageKey = "course2knowledge_lite_visitor_session_id";
  window.sessionStorage?.removeItem(storageKey);
  state.visitorSessionId = "";
  return ensureVisitorSessionId();
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

function setCourseLoadingStatus() {
  setStatus(shouldUsePublicDemoLoadingCopy() ? publicDemoLoadingCopy : "Reading local course store");
}

function isPublicDemo() {
  return Boolean(state.publicDemo);
}

function isLikelyPublicDemoHost() {
  const hostname = String(window.location.hostname || "").toLowerCase();
  return Boolean(hostname && !["localhost", "127.0.0.1", "::1"].includes(hostname));
}

function shouldUsePublicDemoLoadingCopy() {
  return isPublicDemo() || (state.courseStoreLoading && isLikelyPublicDemoHost());
}

function publicDemoNotice() {
  return "云端演示开放课程浏览、课堂笔记、知识节点状态、Hermes 学习对话，以及受控课程导入；导入只处理前 5P，并使用服务器侧 B 站登录态。体验课会定时清理，避免不同访客互相干扰。";
}

function renderExperienceGuide() {
  if (!els.experienceGuide) {
    return;
  }
  if (!isPublicDemo()) {
    els.experienceGuide.hidden = true;
    els.experienceGuide.innerHTML = "";
    return;
  }
  els.experienceGuide.hidden = false;
  els.experienceGuide.innerHTML = `
    <div class="experience-guide-copy">
      <strong>体验说明</strong>
      <span>可以体验：示例课程浏览、课堂笔记阅读、知识节点状态、Hermes 学习对话、受控导入任意 B 站课程前 5P，以及“结束体验”清空本次会话；体验课过期后会自动移除。</span>
    </div>
    <div class="experience-guide-copy">
      <strong>本地部署后可体验</strong>
      <span>完整课程导入、访客自带扫码 / Cookie 登录态、课程删除、笔记写入、书签和阅读进度写入。</span>
    </div>
  `;
}

function renderPublicDemoReadonlyCard() {
  return `
    <section class="readonly-demo-card" aria-label="只读体验边界">
      <strong>云端体验边界</strong>
      <p>${publicDemoNotice()}</p>
    </section>
  `;
}

function guardPublicDemoWrite(target) {
  if (!isPublicDemo()) {
    return false;
  }
  const message = target || publicDemoNotice();
  setStatus("Public demo is read-only");
  if (els.importReceipt) {
    els.importReceipt.innerHTML = `<p class="blocked">${escapeHtml(message)}</p>`;
  }
  return true;
}

async function loadRuntimeMode() {
  const payload = await getJson("/api/runtime");
  const runtime = payload.runtime || {};
  state.publicDemo = Boolean(runtime.public_demo);
  applyRuntimeMode();
  return runtime;
}

function applyRuntimeMode() {
  document.body.classList.toggle("is-public-demo", isPublicDemo());
  renderExperienceGuide();
  const disabled = isPublicDemo();
  const mutableControls = [
    els.bilibiliCookie,
    els.rememberBilibiliCookie,
    els.pasteCookieButton,
    els.qrLoginButton,
    els.clearQrLoginButton,
    els.clearCookieButton,
    els.clearStoredCookieButton,
    els.noteInput,
    els.noteButton,
    els.cardsButton,
    els.progressSelect,
  ].filter(Boolean);
  for (const control of mutableControls) {
    control.disabled = disabled;
    control.setAttribute("aria-disabled", String(disabled));
  }
  if (els.importButton) {
    els.importButton.disabled = false;
    els.importButton.setAttribute("aria-disabled", "false");
  }
  if (els.importUrl) {
    els.importUrl.disabled = false;
    els.importUrl.setAttribute("aria-disabled", "false");
  }
  if (els.bilibiliCookieStatus && disabled) {
    els.bilibiliCookieStatus.textContent = "云端演示使用服务器侧 B 站登录态；访客不需要也不能提交 Cookie。导入会被限制为前 5P。";
  }
  if (els.importReceipt && disabled && !els.importReceipt.innerHTML.trim()) {
    els.importReceipt.innerHTML = renderPublicDemoReadonlyCard();
  }
  if (els.endSessionButton) {
    els.endSessionButton.hidden = !disabled;
  }
  if (els.courseList) {
    renderCourses();
  }
}

function renderCourseLoadingState() {
  state.courseStoreLoading = true;
  const useDemoCopy = shouldUsePublicDemoLoadingCopy();
  const courseLoadingText = useDemoCopy ? publicDemoLoadingCopy : "正在读取课程...";
  const lectureLoadingText = useDemoCopy ? "正在打开 cache 示例课时..." : "正在读取课时...";
  const storeLoadingText = useDemoCopy ? publicDemoLoadingCopy : "正在打开本地课程库...";
  els.courseSelect.innerHTML = `<option value="">${escapeHtml(courseLoadingText)}</option>`;
  els.notesCourseSelect.innerHTML = `<option value="">${escapeHtml(courseLoadingText)}</option>`;
  els.lectureSelect.innerHTML = `<option value="">${escapeHtml(lectureLoadingText)}</option>`;
  els.notesLectureSelect.innerHTML = `<option value="">${escapeHtml(lectureLoadingText)}</option>`;
  els.courseList.innerHTML = `<div class="empty">${escapeHtml(storeLoadingText)}</div>`;
  els.coveragePanel.innerHTML = '<div class="empty">正在检查转写覆盖...</div>';
  els.selectedCourseSummary.innerHTML = '<div class="empty">正在读取课程结构和导入状态...</div>';
  els.lectureAdminList.innerHTML = '<div class="empty">正在展开课时目录...</div>';
  els.cardsList.innerHTML = '<div class="empty">正在读取知识原子...</div>';
  els.segments.innerHTML = '<div class="empty">正在打开当前课时证据...</div>';
  els.notesList.innerHTML = '<div class="empty">正在读取课程笔记...</div>';
  els.bookmarksList.innerHTML = "";
  els.courseMeta.textContent = useDemoCopy ? publicDemoLoadingCopy : "正在打开课程库";
  els.lectureTitle.textContent = useDemoCopy ? publicDemoLoadingCopy : "正在加载课程";
  renderMarkdownUnavailable();
  renderAtomStates();
  renderChatEmptyState();
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

function nextLecture() {
  const current = selectedLecture();
  if (!current) {
    return null;
  }
  const currentSequence = Number(current.sequence);
  const sorted = [...state.lectures].sort(
    (left, right) => Number(left.sequence || 0) - Number(right.sequence || 0),
  );
  return sorted.find((lecture) => Number(lecture.sequence) > currentSequence) || null;
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
  state.courseStoreLoading = false;
  state.lectures = [];
  state.courseId = "";
  state.lectureId = "";
  state.cards = [];
  state.courseCards = [];
  state.chatThreads = [];
  state.chatThreadId = "";
  state.currentHermesAtoms = [];
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
  els.chatLog.innerHTML = "";
  renderChatThreadSelect();
  renderLessonAdvance();
  els.courseMeta.textContent = "尚未选择课程";
  els.lectureTitle.textContent = "等待课程";
  renderMarkdownUnavailable();
  renderAtomStates();
}

async function loadCourses() {
  renderCourseLoadingState();
  setCourseLoadingStatus();
  let payload;
  try {
    payload = await getJson("/api/courses");
  } catch (error) {
    state.courseStoreLoading = false;
    throw error;
  }
  state.courses = payload.courses || [];
  if (!state.courses.length) {
    state.courseStoreLoading = false;
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
  const wasLoadingStore = state.courseStoreLoading;
  state.courseId = courseId;
  state.transientAtomSignals.clear();
  state.cards = [];
  state.courseCards = [];
  renderCourseSelects();
  renderCourses();
  renderAtomStates();
  try {
    const payload = await getJson(`/api/lectures?course_id=${encodeURIComponent(courseId)}`);
    state.lectures = payload.lectures || [];
    state.lectureSequence = publicDemoDefaultLectureSequence(state.lectures);
    renderLectureSelects();
    await loadCoverage();
    await loadReadiness();
    renderSelectedCourseSummary();
    renderLectureAdminList();
    await loadCourseCards();
    await loadReader();
    await loadLearningState();
    await loadChatHistory();
  } finally {
    if (wasLoadingStore) {
      state.courseStoreLoading = false;
      renderChatEmptyState();
    }
  }
}

async function selectLecture(sequence) {
  const parsed = Number(sequence || 1);
  state.lectureSequence = Number.isFinite(parsed) ? parsed : 1;
  state.transientAtomSignals.clear();
  state.currentHermesAtoms = [];
  state.chatThreadId = "";
  els.chatLog.innerHTML = "";
  renderLectureSelects();
  renderLectureAdminList();
  renderChatThreadSelect();
  renderLessonAdvance();
  await loadReader();
  await loadLearningState();
  renderChatEmptyState();
}

async function loadChatHistory(threadId = "") {
  if (!state.courseId) {
    state.chatThreads = [];
    state.chatThreadId = "";
    renderChatThreadSelect();
    renderChatEmptyState();
    return;
  }
  const threadQuery = threadId ? `&thread_id=${encodeURIComponent(threadId)}` : "";
  const visitorQuery = `&visitor_session_id=${encodeURIComponent(ensureVisitorSessionId())}`;
  const payload = await getJson(
    `/api/chat/history?course_id=${encodeURIComponent(state.courseId)}${threadQuery}${visitorQuery}`,
  );
  const thread = payload.thread || {};
  state.chatThreads = Array.isArray(payload.threads) ? payload.threads : [];
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const events = Array.isArray(payload.events) ? payload.events : [];
  state.chatThreadId = thread.thread_id || "";
  renderChatThreadSelect();
  els.chatLog.innerHTML = "";
  if (!messages.length) {
    renderChatEmptyState();
    renderPersistedTeachingControl(events);
    return;
  }
  for (const message of messages) {
    const role = message.role === "user" ? "user" : "assistant";
    const bubble = appendChatBubble(role, message.content || "");
    if (role === "assistant") {
      renderPersistedChatEvents(eventsForMessage(events, message), bubble.querySelector(".chat-events"));
    }
  }
  renderPersistedTeachingControl(events);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function renderChatThreadSelect() {
  if (!els.chatThreadSelect) {
    return;
  }
  if (!state.chatThreads.length) {
    els.chatThreadSelect.innerHTML = '<option value="">新对话</option>';
    els.chatThreadSelect.disabled = false;
    return;
  }
  els.chatThreadSelect.disabled = false;
  els.chatThreadSelect.innerHTML =
    '<option value="">新对话</option>' +
    state.chatThreads
      .map((thread, index) => {
        const countLabel = Number(thread.message_count || 0) ? ` · ${Number(thread.message_count)} 条` : "";
        return `<option value="${index}">${escapeHtml(chatThreadLabel(thread, index + 1))}${escapeHtml(countLabel)}</option>`;
      })
      .join("");
  const selectedIndex = state.chatThreads.findIndex((thread) => thread.thread_id === state.chatThreadId);
  els.chatThreadSelect.value = selectedIndex >= 0 ? String(selectedIndex) : "";
}

function chatThreadLabel(thread, fallbackIndex) {
  const title = String(thread.title || "").trim();
  const updated = String(thread.updated_at || thread.created_at || "").slice(0, 16).replace("T", " ");
  const prefix = title || `对话 ${fallbackIndex}`;
  const clipped = prefix.length > 28 ? `${prefix.slice(0, 27)}…` : prefix;
  return updated ? `${clipped} · ${updated}` : clipped;
}

async function importCollection() {
  const sourceUrl = els.importUrl.value.trim();
  if (!sourceUrl) {
    els.importReceipt.textContent = "粘贴一个 Bilibili 合集链接。";
    setStatus("Import needs a URL");
    return;
  }
  const publicDemoImport = isPublicDemo();
  els.importButton.disabled = true;
  els.importReceipt.innerHTML = renderImportStatusCard({
    run: { status: "queued", stage: "queued", total_lectures: 0, completed_lectures: 0, failed_lectures: 0 },
    events: [],
    readiness: {},
    promotion: {},
    progress: {},
    runId: "",
    authText: publicDemoImport
      ? "正在提交云端受控导入：使用服务器侧 B 站登录态，只处理课程前 5P。"
      : "正在把导入任务交给本机后端。",
  });
  setStatus("Importing Bilibili collection");
  try {
    const bilibiliCookie = publicDemoImport ? "" : els.bilibiliCookie ? els.bilibiliCookie.value.trim() : "";
    const importPayload = { source_url: sourceUrl };
    const rememberCookie = !publicDemoImport && Boolean(els.rememberBilibiliCookie?.checked);
    if (publicDemoImport) {
      importPayload.max_lectures = 5;
    } else if (bilibiliCookie) {
      importPayload.bilibili_cookie = bilibiliCookie;
    } else if (state.qrLoginId && state.qrLoginStatus === "succeeded") {
      importPayload.bilibili_qr_login_id = state.qrLoginId;
    }
    if (rememberCookie && (bilibiliCookie || importPayload.bilibili_qr_login_id)) {
      importPayload.remember_bilibili_cookie = true;
    }
    const payload = await sendJson("/api/import", importPayload);
    if (els.bilibiliCookie) {
      els.bilibiliCookie.value = "";
    }
    const usedQrLogin = !publicDemoImport && Boolean(importPayload.bilibili_qr_login_id);
    if (usedQrLogin) {
      clearQrLoginState({ silent: true });
    }
    const run = payload.run || {};
    const authText =
        publicDemoImport
          ? "云端导入已接收：服务器侧登录态会拉取课程信息，前台没有接触 Cookie；本次最多导入前 5P。"
          : bilibiliCookie
          ? rememberCookie
            ? "Cookie 已发送并保存到本机登录态，前台输入框已清空。"
            : "Cookie 已临时发送，前台已清空。"
          : usedQrLogin
            ? rememberCookie
              ? "扫码登录态已保存到本机，并用于本次导入；前台没有接触 Cookie。"
              : "扫码登录态已交给本机后端用于本次导入，前台没有接触 Cookie。"
            : "未提供临时 Cookie；如本机已保存登录态，本次会自动使用。";
    els.importReceipt.innerHTML = renderImportStatusCard({
      run,
      events: [],
      readiness: {},
      promotion: {},
      progress: {},
      runId: payload.run_id || run.run_id || "",
      authText,
    });
    pollImportStatus(payload.run_id || run.run_id || "");
    if (!publicDemoImport) {
      loadBilibiliCookieStatus().catch(() => {});
    }
    setStatus("Import accepted");
  } catch (error) {
    els.importReceipt.innerHTML = renderImportErrorCard(error.message, {});
    setStatus("Import failed");
  } finally {
    els.importButton.disabled = false;
  }
}

async function pasteBilibiliCookieFromClipboard() {
  if (guardPublicDemoWrite("当前模式不读取或发送 B 站 Cookie。")) {
    return;
  }
  if (!els.bilibiliCookie || !navigator.clipboard?.readText) {
    els.importReceipt.innerHTML = '<p class="blocked">当前浏览器不支持从剪贴板读取，请手动粘贴 Cookie。</p>';
    return;
  }
  try {
    const text = await navigator.clipboard.readText();
    els.bilibiliCookie.value = text.trim();
    els.importReceipt.innerHTML = '<p class="citation">Cookie 已填入临时输入框；只会在点击导入时发送一次。</p>';
  } catch (error) {
    els.importReceipt.innerHTML = `<p class="blocked">${escapeHtml(error.message || "剪贴板读取失败，请手动粘贴 Cookie。")}</p>`;
  }
}

function clearBilibiliCookieInput() {
  if (guardPublicDemoWrite("当前模式没有可清空的临时 Cookie。")) {
    return;
  }
  if (els.bilibiliCookie) {
    els.bilibiliCookie.value = "";
  }
  els.importReceipt.innerHTML = '<p class="citation">Cookie 临时输入已清空。</p>';
}

async function loadBilibiliCookieStatus() {
  if (!els.bilibiliCookieStatus) {
    return;
  }
  if (isPublicDemo()) {
    els.bilibiliCookieStatus.textContent = "当前模式已关闭 B 站登录态读取与写入。";
    return;
  }
  try {
    const payload = await getJson("/api/bilibili/cookie");
    renderBilibiliCookieStatus(payload.auth || {});
  } catch (error) {
    els.bilibiliCookieStatus.textContent = `本机登录态读取失败：${error.message}`;
  }
}

function renderBilibiliCookieStatus(auth) {
  if (!els.bilibiliCookieStatus) {
    return;
  }
  const names = Array.isArray(auth.cookie_names) ? auth.cookie_names : [];
  if (auth.stored && names.length) {
    const updated = auth.updated_at ? `；更新时间 ${String(auth.updated_at).slice(0, 19).replace("T", " ")}` : "";
    els.bilibiliCookieStatus.textContent = `已保存 B 站登录态：${names.join(", ")}${updated}`;
    return;
  }
  els.bilibiliCookieStatus.textContent = "未保存 B 站登录态；可以临时粘贴 Cookie 或扫码登录。";
}

async function clearStoredBilibiliCookie() {
  if (guardPublicDemoWrite("当前模式不允许修改本机保存的 B 站登录态。")) {
    return;
  }
  const payload = await sendJson("/api/bilibili/cookie/clear", {});
  renderBilibiliCookieStatus(payload.auth || {});
  if (els.importReceipt) {
    els.importReceipt.innerHTML = '<p class="citation">已清除本机保存的 B 站登录态。</p>';
  }
}

async function startBilibiliQrLogin() {
  if (guardPublicDemoWrite("当前模式不支持扫码登录。")) {
    return;
  }
  if (!els.qrLoginPanel) {
    return;
  }
  clearQrLoginState({ silent: true });
  els.qrLoginButton.disabled = true;
  els.qrLoginPanel.classList.remove("is-hidden");
  els.qrLoginPanel.innerHTML = '<p class="citation">正在向 B 站请求扫码二维码...</p>';
  try {
    const payload = await sendJson("/api/bilibili/login/qrcode", {});
    state.qrLoginId = String(payload.login_id || "");
    state.qrLoginStatus = String(payload.login_status || "pending");
    state.qrLoginImage = String(payload.qr_svg || "");
    renderQrLoginPanel(payload);
    pollBilibiliQrLogin();
  } catch (error) {
    els.qrLoginPanel.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
  } finally {
    els.qrLoginButton.disabled = false;
  }
}

function pollBilibiliQrLogin() {
  if (!state.qrLoginId) {
    return;
  }
  if (state.qrLoginPollTimer) {
    window.clearInterval(state.qrLoginPollTimer);
  }
  const refresh = async () => {
    if (!state.qrLoginId) {
      return;
    }
    try {
      const payload = await getJson(`/api/bilibili/login/qrcode/status?login_id=${encodeURIComponent(state.qrLoginId)}`);
      state.qrLoginStatus = String(payload.login_status || "");
      if (!payload.login_id && state.qrLoginStatus !== "succeeded") {
        state.qrLoginId = "";
      }
      renderQrLoginPanel(payload);
      if (["succeeded", "expired", "failed"].includes(state.qrLoginStatus)) {
        window.clearInterval(state.qrLoginPollTimer);
        state.qrLoginPollTimer = null;
      }
    } catch (error) {
      window.clearInterval(state.qrLoginPollTimer);
      state.qrLoginPollTimer = null;
      els.qrLoginPanel.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
    }
  };
  refresh();
  state.qrLoginPollTimer = window.setInterval(refresh, 2500);
}

function renderQrLoginPanel(payload) {
  if (!els.qrLoginPanel) {
    return;
  }
  const status = String(payload.login_status || "pending");
  const ready = status === "succeeded";
  const ttl = Number(payload.ttl_seconds || 0);
  const qrImageSource = payload.qr_svg || state.qrLoginImage;
  const qrImage = qrImageSource && !["expired", "failed"].includes(status)
    ? `<img class="qr-login-image" src="${escapeHtml(qrImageSource)}" alt="Bilibili 扫码登录二维码" />`
    : "";
  els.qrLoginPanel.classList.remove("is-hidden");
  els.qrLoginPanel.innerHTML = `
    ${qrImage}
    <div class="qr-login-copy">
      <p class="${ready ? "ready-text" : status === "failed" || status === "expired" ? "blocked" : "citation"}">${escapeHtml(
        payload.message || "等待扫码",
      )}</p>
      <p class="field-hint">${ready ? "已获得本次导入可用的后端登录态；Cookie 不会显示到前台。" : `剩余 ${ttl} 秒，扫码后请在手机上确认。`}</p>
    </div>
  `;
}

async function clearBilibiliQrLogin() {
  if (guardPublicDemoWrite("当前模式没有可清空的扫码登录状态。")) {
    return;
  }
  const loginId = state.qrLoginId;
  if (loginId) {
    try {
      await sendJson("/api/bilibili/login/qrcode/clear", { login_id: loginId });
    } catch (_error) {
      // Clearing is best-effort; local state is still dropped.
    }
  }
  clearQrLoginState();
}

function clearQrLoginState(options = {}) {
  if (state.qrLoginPollTimer) {
    window.clearInterval(state.qrLoginPollTimer);
    state.qrLoginPollTimer = null;
  }
  state.qrLoginId = "";
  state.qrLoginStatus = "";
  state.qrLoginImage = "";
  if (els.qrLoginPanel) {
    els.qrLoginPanel.classList.add("is-hidden");
    els.qrLoginPanel.innerHTML = "";
  }
  if (!options.silent && els.importReceipt) {
    els.importReceipt.innerHTML = '<p class="citation">扫码登录状态已清空。</p>';
  }
}

function pollImportStatus(runId) {
  if (!runId) {
    return;
  }
  if (state.importPollTimer) {
    window.clearInterval(state.importPollTimer);
  }
  const refresh = async () => {
    const payload = await getJson(`/api/import/status?run_id=${encodeURIComponent(runId)}`);
    const run = payload.run || {};
    els.importReceipt.innerHTML = renderImportStatusCard({
      run,
      events: payload.events || [],
      readiness: payload.readiness || {},
      promotion: payload.promotion || {},
      progress: payload.progress || {},
      runId,
      authText: "",
    });
    if (run.course_id) {
      state.courseId = run.course_id;
    }
    if (["completed", "partial", "failed", "cancelled"].includes(run.status)) {
      window.clearInterval(state.importPollTimer);
      state.importPollTimer = null;
      await loadCourses();
      if (run.course_id) {
        await selectCourse(run.course_id);
      }
    }
  };
  refresh().catch((error) => {
    els.importReceipt.innerHTML = renderImportErrorCard(error.message, {});
  });
  state.importPollTimer = window.setInterval(() => {
    refresh().catch((error) => {
      els.importReceipt.innerHTML = renderImportErrorCard(error.message, {});
      window.clearInterval(state.importPollTimer);
      state.importPollTimer = null;
    });
  }, 1800);
}

async function restoreLatestImportStatus() {
  if (!els.importReceipt || els.importReceipt.innerHTML.trim()) {
    return;
  }
  const payload = await getJson("/api/import/status");
  const latestRun = Array.isArray(payload.runs) ? payload.runs[0] : null;
  if (!latestRun || !["queued", "running", "partial", "failed", "cancelled"].includes(String(latestRun.status || ""))) {
    return;
  }
  const detail = await getJson(`/api/import/status?run_id=${encodeURIComponent(latestRun.run_id || "")}`);
  const run = detail.run || latestRun;
  els.importReceipt.innerHTML = renderImportStatusCard({
    run,
    events: detail.events || [],
    readiness: detail.readiness || {},
    promotion: detail.promotion || {},
    progress: detail.progress || {},
    runId: run.run_id || latestRun.run_id || "",
    authText: "",
  });
  if (["queued", "running"].includes(String(run.status || ""))) {
    pollImportStatus(run.run_id || latestRun.run_id || "");
  }
}

function renderImportStatusCard({ run = {}, events = [], readiness = {}, promotion = {}, progress = {}, runId = "", authText = "" }) {
  const effective = effectiveImportStatus({ run, events, readiness, promotion, progress });
  const phase = importPhaseCopy(effective.run.stage, effective.run.status, promotion);
  const counts = importProgressCounts(effective.run, effective.readiness);
  const percent = counts.total > 0 ? Math.round((counts.done / counts.total) * 100) : 0;
  const progressStyle = counts.total > 0 ? `width: ${Math.max(0, Math.min(percent, 100))}%` : "";
  const progressClass = counts.total > 0 ? "" : " is-indeterminate";
  const gate = importGateSummary(effective.run, effective.readiness);
  const issue = importIssueSummary(effective.run, effective.events, promotion, progress);
  const metrics = importMetricCards(effective.readiness, promotion);
  const timeline = importTimeline(effective.events);
  const details = importTechnicalDetails(effective.run, runId || effective.run.run_id || "", promotion, progress);
  return `
    <section class="import-status-card ${phase.className}" aria-label="导入进度">
      <div class="import-status-head">
        <div>
          <p class="import-status-kicker">${escapeHtml(phase.kicker)}</p>
          <h3>${escapeHtml(phase.title)}</h3>
          <p>${escapeHtml(phase.body)}</p>
          ${authText ? `<p class="field-hint">${escapeHtml(authText)}</p>` : ""}
        </div>
        <span class="import-status-pill">${escapeHtml(phase.badge)}</span>
      </div>
      <div class="import-progress-track${progressClass}" aria-label="导入进度">
        <span style="${progressStyle}"></span>
      </div>
      <div class="import-progress-row">
        <strong>${counts.label}</strong>
        <span>${gate}</span>
      </div>
      ${issue}
      <div class="import-metric-grid">${metrics}</div>
      ${timeline}
      ${details}
    </section>
  `;
}

function effectiveImportStatus({ run, events, readiness, promotion, progress }) {
  const progressRun = progress?.available && progress.run ? progress.run : null;
  const progressEvents = progress?.available && Array.isArray(progress.events) ? progress.events : [];
  const progressReadiness = progress?.available && progress.readiness ? progress.readiness : null;
  const effectiveRun = {
    ...run,
    ...(progressRun || {}),
    run_id: run.run_id || progressRun?.run_id || "",
  };
  const effectiveReadiness = progressReadiness && Number(progressReadiness.lecture_count || 0) > 0 ? progressReadiness : readiness || {};
  const effectiveEvents = progressEvents.length ? progressEvents : events || [];
  const candidate = promotion?.candidate || {};
  if (!Number(effectiveReadiness.lecture_count || 0) && Number(candidate.lecture_count || 0) > 0) {
    return { run: effectiveRun, events: effectiveEvents, readiness: candidate };
  }
  return { run: effectiveRun, events: effectiveEvents, readiness: effectiveReadiness };
}

function importPhaseCopy(stage, status, promotion = {}) {
  const cleanedStage = String(stage || "queued");
  const cleanedStatus = String(status || "queued");
  const decision = String(promotion?.decision || "");
  if (cleanedStatus === "failed" || ["promotion_blocked", "failed", "temp_import_failed"].includes(cleanedStage)) {
    const isProbeSubset = decision === "blocked_probe_subset";
    const isPromotionBlocked = cleanedStage === "promotion_blocked" || ["blocked", "blocked_probe_subset"].includes(decision);
    return {
      kicker: "需要处理",
      title: isProbeSubset ? "探针导入已完成，未写入课程库" : isPromotionBlocked ? "入库保护阻断，当前课程库未改动" : "导入失败",
      body: isPromotionBlocked
        ? "临时库生成结果已保留在本次 run 中；系统没有把它写入正式课程库，下面会说明原因。"
        : "导入链路已经停止，下面会给出失败原因和建议。",
      badge: isProbeSubset ? "探针完成" : isPromotionBlocked ? "保护阻断" : "失败",
      className: isProbeSubset ? "is-warning" : "is-error",
    };
  }
  if (cleanedStatus === "cancelled" || cleanedStage === "cancelled") {
    return {
      kicker: "已取消",
      title: "导入已取消",
      body: "本次导入已停止，当前课程库保持不变。",
      badge: "已取消",
      className: "is-warning",
    };
  }
  if (decision === "merged_new_course" || cleanedStage === "merged_new_course") {
    return {
      kicker: "已完成",
      title: "新课程已合并入本地库",
      body: "临时库已通过就绪检查，系统已把这门新课加入课程库，并保留原有课程数据。",
      badge: "完成",
      className: "is-ready",
    };
  }
  if (decision === "replaced_same_course" || decision === "promoted" || cleanedStage === "replaced_same_course" || cleanedStage === "promoted") {
    return {
      kicker: "已完成",
      title: "同课程重导入已更新",
      body: "候选数据通过同课程非回退检查，系统只更新这门课程，不影响其他课程。",
      badge: "完成",
      className: "is-ready",
    };
  }
  const copy = {
    queued: ["准备中", "已排队，准备解析课程", "后端已经收到任务，马上开始解析课程列表。", "排队中"],
    temp_import: ["安全导入", "正在临时库处理课程", "系统会先在临时库生成字幕、笔记、知识原子和关口，通过检查后再决定合并新课或更新同课。", "处理中"],
    collection_expand: ["解析课程", "正在读取 B 站课程列表", "正在把合集/系列课拆成课时。", "解析中"],
    source_acquisition: ["获取材料", "正在获取字幕和课时材料", "如果 B 站需要登录，这一步会依赖扫码或 Cookie。", "获取中"],
    lecture_compile: ["生成内容", "正在生成笔记、知识原子和关口", "每一讲会依次生成可学习的结构化内容。", "生成中"],
    ready_gate: ["就绪检查", "正在检查课程是否完整可用", "会核对字幕、笔记、知识原子和关口是否都准备好。", "检查中"],
    ready_gate_blocked: ["就绪检查", "课程导入不完整", "至少有一部分课时缺少字幕、笔记、知识原子或关口。", "未就绪"],
  };
  const selected = copy[cleanedStage] || copy[cleanedStatus] || ["导入中", "正在处理课程", "导入链路仍在运行。", "运行中"];
  return {
    kicker: selected[0],
    title: selected[1],
    body: selected[2],
    badge: selected[3],
    className: "is-running",
  };
}

function importProgressCounts(run, readiness) {
  const total = Number(run.total_lectures || readiness.lecture_count || 0);
  const done = Number(run.completed_lectures || readiness.ready_lecture_count || 0);
  const failed = Number(run.failed_lectures || 0);
  const isTerminal = ["completed", "partial", "failed", "cancelled"].includes(String(run.status || ""));
  const pending = Math.max(total - done - failed, 0);
  if (total <= 0) {
    if (String(run.status || "") === "failed") {
      return { total: 0, done: 0, failed: 0, label: "没有解析到可导入课时" };
    }
    return { total: 0, done: 0, failed: 0, label: "正在确认课时数量" };
  }
  if (failed) {
    const pendingLabel = pending && !isTerminal ? `，${pending} 讲待处理` : "";
    return { total, done, failed, pending, label: `${done}/${total} 讲可用，${failed} 讲失败${pendingLabel}` };
  }
  if (!isTerminal && pending) {
    return { total, done, failed, pending, label: `${done}/${total} 讲可用，${pending} 讲待处理` };
  }
  return { total, done, failed, pending, label: `${done}/${total} 讲可用` };
}

function importGateSummary(run, readiness) {
  const total = Number(readiness.lecture_count || 0);
  const ready = Number(readiness.ready_lecture_count || 0);
  const stage = String(run.stage || "");
  const isTerminal = ["completed", "partial", "failed", "cancelled"].includes(String(run.status || ""));
  if (!total) {
    return "就绪检查会在解析到课时后开始";
  }
  if (["merged_new_course", "replaced_same_course", "promoted"].includes(stage) && ready === total) {
    return `已入库：${ready}/${total} 讲`;
  }
  if (stage === "promotion_blocked" && ready === total) {
    return `临时库已就绪：${ready}/${total} 讲，正式库未改动`;
  }
  if (!isTerminal) {
    return `正在处理：${ready}/${total} 讲已生成完整材料`;
  }
  if (readiness.ready) {
    return `就绪检查通过：${ready}/${total} 讲`;
  }
  if (ready <= 0) {
    return "没有可用课时，未覆盖当前课程库";
  }
  return `就绪检查未通过：${ready}/${total} 讲可用`;
}

function importIssueSummary(run, events, promotion, progress) {
  const latestFailure = [...(events || [])].reverse().find((event) =>
    ["failed", "lecture_failed", "lecture_not_ready", "run_failed", "worker_failed", "promotion_blocked", "temp_import_failed"].includes(
      String(event.event_type || event.status || ""),
    ),
  );
  const stage = String(run.stage || "");
  const failureMessage = latestFailure?.payload?.error || latestFailure?.message || progress?.error || "";
  const rawMessage = stage === "promotion_blocked" ? failureMessage || promotion?.reason : failureMessage || promotion?.reason || "";
  const message = humanizeImportFailureMessage(rawMessage, run);
  const isIssue =
    String(run.status || "") === "failed" ||
    stage === "promotion_blocked" ||
    stage === "temp_import_failed" ||
    latestFailure;
  if (!isIssue || !message) {
    return "";
  }
  return `
    <div class="import-alert">
      <strong>${escapeHtml(importErrorTitle(latestFailure, run, rawMessage))}</strong>
      <p>${escapeHtml(message)}</p>
      <p class="field-hint">${escapeHtml(importRecoveryHint(rawMessage || message, latestFailure))}</p>
    </div>
  `;
}

function humanizeImportFailureMessage(message, run = {}) {
  const text = String(message || "");
  const lower = text.toLowerCase();
  const total = Number(run.total_lectures || 0);
  if (lower.includes("bilibili page did not expose subtitle metadata")) {
    const lectureText = total > 0 ? `${total}讲` : "这些课时";
    return `B 站页面没有返回可用字幕元数据，所以${lectureText}都无法生成转写；没有转写，笔记、知识原子和关口也不会继续生成。当前课程库没有被覆盖。`;
  }
  if (lower.includes("unsupported bilibili source url")) {
    return "这个链接不是当前导入器能识别的 B 站视频、合集或系列课链接，请换成课程页、合集页或系列课页后重试。";
  }
  if (!text) {
    return "导入链路停止了，但后端没有返回更具体的错误；当前课程库没有被覆盖。";
  }
  return text;
}

function importErrorTitle(event, run, message = "") {
  const type = String(event?.payload?.error_type || "");
  const lower = String(message || "").toLowerCase();
  if (lower.includes("bilibili page did not expose subtitle metadata")) {
    return "没有拿到 B 站字幕";
  }
  if (String(run.stage || "") === "promotion_blocked" || String(event?.event_type || "") === "promotion_blocked") {
    return "入库保护阻断";
  }
  if (type) {
    return `失败类型：${type}`;
  }
  return "导入遇到问题";
}

function importRecoveryHint(message, event) {
  const text = `${message || ""} ${event?.payload?.error_type || ""}`.toLowerCase();
  if (text.includes("探针") || text.includes("probe")) {
    return "这是限制课时数的测试导入，默认不会写入正式库；需要正式导入时，请取消课时限制后重新导入。";
  }
  if (text.includes("候选导入质量低于同一课程") || text.includes("同一课程")) {
    return "这是同课程重导入保护：候选数据少于旧数据时不会覆盖。可以查看技术详情确认缺少哪一类材料。";
  }
  if (text.includes("bilibili page did not expose subtitle metadata") || text.includes("subtitle metadata")) {
    return "下一步：先扫码登录或粘贴 Bilibili Cookie 后重试；如果课程本身没有字幕，就需要接入公开 ASR 入口。失败数据不会覆盖当前课程库。";
  }
  if (text.includes("cookie") || text.includes("login") || text.includes("auth") || text.includes("subtitle")) {
    return "下一步：先扫码登录或临时粘贴 Bilibili Cookie，再重新导入。失败数据不会覆盖当前课程库。";
  }
  if (text.includes("deepseek") || text.includes("api") || text.includes("model") || text.includes("provider")) {
    return "检查模型服务/API Key 配置后重试；失败前的当前课程库不会被覆盖。";
  }
  if (text.includes("transcript") || text.includes("字幕") || text.includes("转写")) {
    return "这通常是字幕不可用；后续需要 ASR 或手动转写入口补齐。";
  }
  return "当前本地库保持不变；可以展开技术详情定位 run_id，再重试导入。";
}

function importMetricCards(readiness, promotion) {
  const previous = Number(promotion?.previous_course?.lecture_count || 0) > 0 ? promotion.previous_course : promotion?.previous?.best || {};
  const items = [
    ["转写", `${Number(readiness.transcript_ready_count || 0)}/${Number(readiness.lecture_count || 0)}`],
    ["笔记", Number(readiness.note_ready_count || 0)],
    ["知识原子", Number(readiness.atom_ready_count || 0)],
    ["关口", Number(readiness.gate_ready_count || 0)],
  ];
  const cards = items
    .map(([label, value]) => `<span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(label)}</small></span>`)
    .join("");
  const previousText = Number(previous.lecture_count || 0)
    ? `<p class="field-hint">对比基线：转写 ${Number(previous.transcript_ready_count || 0)}/${Number(previous.lecture_count || 0)}，笔记 ${Number(
        previous.note_ready_count || 0,
      )}，原子 ${Number(previous.atom_ready_count || 0)}，关口 ${Number(previous.gate_ready_count || 0)}</p>`
    : "";
  return `${cards}${previousText}`;
}

function importTimeline(events) {
  const visibleEvents = (events || []).slice(-5).reverse();
  if (!visibleEvents.length) {
    return '<div class="import-timeline"><p class="field-hint">等待后端返回第一条导入事件。</p></div>';
  }
  return `
    <ol class="import-timeline">
      ${visibleEvents
        .map((event) => {
          const label = importEventLabel(event);
          const time = String(event.created_at || "").slice(11, 19);
          const suffix = event.message ? `：${event.message}` : "";
          return `<li><span>${escapeHtml(time || "刚刚")}</span><p>${escapeHtml(label + suffix)}</p></li>`;
        })
        .join("")}
    </ol>
  `;
}

function importEventLabel(event) {
  const type = String(event.event_type || "");
  const labels = {
    import_requested: "任务已提交",
    temp_import_started: "开始临时库导入",
    parallelism_resolved: "并发策略已确定",
    stage_start: "阶段开始",
    stage_completed: "阶段完成",
    lecture_completed: "课时完成",
    lecture_failed: "课时失败",
    lecture_not_ready: "课时未就绪",
    ready_gate: "就绪检查",
    promotion_completed: "入库完成",
    promotion_blocked: "入库保护阻断",
    temp_import_failed: "临时导入失败",
    worker_failed: "导入任务失败",
    run_failed: "导入失败",
    run_cancelled: "导入取消",
    run_interrupted: "导入已中断",
  };
  return labels[type] || type || "状态更新";
}

function importTechnicalDetails(run, runId, promotion, progress) {
  const stage = run.stage || "queued";
  const status = run.status || "queued";
  const artifactSummary = progress?.artifact_summary ? JSON.stringify(progress.artifact_summary.by_type || {}) : "";
  const progressEvents = Array.isArray(progress?.events) ? progress.events : [];
  const parallelismEvent = [...progressEvents].reverse().find((event) => event?.payload?.effective_parallelism || event?.payload?.parallelism);
  const effectiveParallelism = parallelismEvent?.payload?.effective_parallelism || parallelismEvent?.payload?.parallelism || {};
  const requestedParallelism = parallelismEvent?.payload?.requested_parallelism || {};
  const profile = parallelismEvent?.payload?.parallelism_profile || {};
  const guard = parallelismEvent?.payload?.parallelism_guard || {};
  const parallelismText = effectiveParallelism.lecture_workers
    ? `课时 ${effectiveParallelism.lecture_workers} / 分块 ${effectiveParallelism.dossier_chunk_workers} / 请求 ${effectiveParallelism.dossier_request_concurrency}`
    : "";
  const requestedText = requestedParallelism.lecture_workers
    ? `请求值：课时 ${requestedParallelism.lecture_workers} / 分块 ${requestedParallelism.dossier_chunk_workers} / 请求 ${requestedParallelism.dossier_request_concurrency}`
    : "";
  return `
    <details class="import-debug">
      <summary>技术详情</summary>
      <p>run_id: ${escapeHtml(runId || run.run_id || "")}</p>
      <p>状态：${escapeHtml(status)} / ${escapeHtml(stage)}</p>
      ${progress?.stale ? `<p>旧任务：服务重启前的导入已中断，需要重新导入。</p>` : ""}
      ${parallelismText ? `<p>实际并发：${escapeHtml(parallelismText)}</p>` : ""}
      ${requestedText ? `<p>${escapeHtml(requestedText)}</p>` : ""}
      ${profile?.profile_id ? `<p>并发 Profile：${escapeHtml(profile.profile_id)}</p>` : ""}
      ${guard?.guard_id ? `<p>并发保护：${escapeHtml(guard.guard_id)}</p>` : ""}
      ${promotion?.decision ? `<p>入库决策：${escapeHtml(promotion.decision)}</p>` : ""}
      ${promotion?.course_match ? `<p>课程匹配：${escapeHtml(promotion.course_match)}</p>` : ""}
      ${artifactSummary ? `<p>产物统计：${escapeHtml(artifactSummary)}</p>` : ""}
    </details>
  `;
}

function renderImportErrorCard(message, payload) {
  return `
    <section class="import-status-card is-error" aria-label="导入错误">
      <div class="import-status-head">
        <div>
          <p class="import-status-kicker">请求失败</p>
          <h3>导入没有启动</h3>
          <p>${escapeHtml(message || payload?.error || "前台请求后端失败。")}</p>
        </div>
        <span class="import-status-pill">失败</span>
      </div>
      <div class="import-alert">
        <strong>可以直接重试</strong>
        <p class="field-hint">如果连续失败，请检查后端是否仍在 3014 端口运行。</p>
      </div>
    </section>
  `;
}

function renderCourses() {
  if (!state.courses.length) {
    els.courseList.innerHTML = '<div class="empty">本地课程库暂无课程。</div>';
    return;
  }
  els.courseList.innerHTML = state.courses
    .map(
      (course) => {
        const courseAction = isPublicDemo()
          ? '<span class="readonly-pill" title="当前模式不允许删除课程">只读</span>'
          : `<button class="ghost-button delete-course-button" type="button" data-course-id="${escapeHtml(
              course.course_id,
            )}" title="删除课程">删除</button>`;
        return `
        <article class="course-item ${course.course_id === state.courseId ? "is-active" : ""}" data-course-id="${escapeHtml(
          course.course_id,
        )}">
          <div>
            <p class="item-title">${escapeHtml(course.title || course.course_id)}</p>
            <p class="item-meta">${Number(course.lecture_count || 0)} 课时 / ${Number(
              course.lecture_transcript_count || 0,
            )} 有转写</p>
            <p class="item-meta">Hermes：${escapeHtml(bindingStatusLabel(course.web_hermes_binding_status))}</p>
            <p class="citation">${escapeHtml(course.course_id)}</p>
          </div>
          ${courseAction}
        </article>
      `;
      },
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
  if (guardPublicDemoWrite("当前模式不允许删除课程。")) {
    return;
  }
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

async function loadReadiness() {
  if (!state.courseId) {
    state.readiness = null;
    return;
  }
  const payload = await getJson(`/api/readiness?course_id=${encodeURIComponent(state.courseId)}`);
  state.readiness = payload.readiness || null;
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
  const readiness = state.readiness || {};
  const bindingLabel = bindingStatusLabel(course.web_hermes_binding_status);
  const transcriptReadyCount = Number(course.lecture_transcript_count || 0);
  const lectureCount = Number(course.lecture_count || 0);
  const missingTranscriptCount = Math.max(lectureCount - transcriptReadyCount, 0);
  const transcriptHint = missingTranscriptCount
    ? `<p class="field-hint">${missingTranscriptCount} 讲暂无可用字幕；课程目录仍保留完整边界，并使用有转写课时展示主链路。</p>`
    : "";
  els.selectedCourseSummary.innerHTML = `
    <div class="summary-line">
      <span>课程名称</span>
      <strong>${escapeHtml(course.title || course.course_id)}</strong>
    </div>
    <div class="summary-line">
      <span>来源</span>
      <strong>${escapeHtml(displaySourceUrl(course.source_url))}</strong>
    </div>
    <div class="summary-line">
      <span>课时状态</span>
      <strong>${transcriptReadyCount} / ${lectureCount} 有转写</strong>
    </div>
    ${transcriptHint}
    <div class="summary-line">
      <span>导入 Ready Gate</span>
      <strong>${Number(readiness.ready_lecture_count || 0)} / ${Number(
        readiness.lecture_count || course.lecture_count || 0,
      )} 课时</strong>
    </div>
    <div class="summary-line">
      <span>知识原子</span>
      <strong>${Number(readiness.total_atom_count || state.courseCards.length || 0)}</strong>
    </div>
    <div class="summary-line">
      <span>关口</span>
      <strong>${Number(readiness.total_gate_count || 0)}</strong>
    </div>
    <div class="summary-line">
      <span>证据片段</span>
      <strong>${Number(coverage.total_segment_count || 0)}</strong>
    </div>
    <div class="summary-line">
      <span>Hermes 接入</span>
      <strong>${escapeHtml(bindingLabel)}</strong>
    </div>
  `;
}

function bindingStatusLabel(status) {
  if (status === "bound") {
    return "已接入正式课程";
  }
  if (status === "blocked") {
    return "暂不接入";
  }
  return "Web Lite 已接入（本地课程隔离）";
}

function renderLectureAdminList() {
  if (!state.lectures.length) {
    els.lectureAdminList.innerHTML = '<div class="empty">还没有加载课时。</div>';
    return;
  }
  const readinessByLecture = new Map(
    ((state.readiness && state.readiness.lectures) || []).map((item) => [String(item.lecture_id || ""), item]),
  );
  els.lectureAdminList.innerHTML = state.lectures
    .map(
      (lecture) => {
        const readiness = readinessByLecture.get(String(lecture.lecture_id || "")) || {};
        const missing = (readiness.missing || []).join(" / ");
        return `
        <button class="lecture-row ${Number(lecture.sequence) === Number(state.lectureSequence) ? "is-active" : ""}"
          type="button"
          data-sequence="${escapeHtml(lecture.sequence)}">
          <span>${escapeHtml(lecture.sequence)}. ${escapeHtml(lecture.title || lecture.lecture_id)}</span>
          <small>${Number(readiness.atom_count || 0)} 原子 / ${Number(readiness.gate_count || 0)} 关口 / ${
            readiness.ready ? "ready" : escapeHtml(missing || "not_ready")
          }</small>
        </button>
      `;
      },
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
      (segment) => {
        const bookmarkAction = isPublicDemo()
          ? '<span class="readonly-pill">只读</span>'
          : `<button class="ghost-button bookmark-segment" type="button" data-segment-id="${escapeHtml(
              segment.segment_id,
            )}" title="收藏片段">收藏</button>`;
        return `
        <article class="segment">
          <div class="segment-head">
            <p class="segment-title">${secondsLabel(segment.start_seconds)}-${secondsLabel(segment.end_seconds)}</p>
            ${bookmarkAction}
          </div>
          <p>${escapeHtml(segment.text)}</p>
          <p class="citation">${escapeHtml(segment.segment_id)}</p>
        </article>
      `;
      },
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
  await loadVisualEvidence();
  renderBookmarks(bookmarksPayload.bookmarks || []);
  const progress = (progressPayload.progress || [])[0] || {};
  state.currentProgressStatus = progress.status || "not_started";
  els.progressSelect.value = state.currentProgressStatus;
  renderAtomStates();
}

async function loadVisualEvidence() {
  if (!state.courseId || !state.lectureId) {
    renderVisualEvidence([]);
    return;
  }
  const payload = await getJson(
    `/api/visuals?course_id=${encodeURIComponent(state.courseId)}&lecture_id=${encodeURIComponent(state.lectureId)}`,
  );
  renderVisualEvidence(payload.visuals || []);
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
      (card) => {
        const bookmarkAction = isPublicDemo()
          ? '<span class="readonly-pill">只读</span>'
          : `<button class="ghost-button bookmark-card" type="button" data-card-id="${escapeHtml(
              card.card_id,
            )}" title="收藏知识原子">收藏</button>`;
        return `
        <article class="knowledge-card">
          <div class="segment-head">
            <p class="segment-title">${escapeHtml(card.title || card.card_id)}</p>
            ${bookmarkAction}
          </div>
          <p>${escapeHtml(card.body)}</p>
          <p class="citation">${escapeHtml(card.lecture_id)} / ${escapeHtml((card.source_segment_ids || []).join(", "))}</p>
          <p class="tags">${(card.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</p>
        </article>
      `;
      },
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
  state.currentHermesAtoms = [];
  renderLearningSignals(null);
  if (state.courseStoreLoading) {
    els.atomProgressSummary.textContent = "正在读取知识节点";
    els.atomStateList.innerHTML = '<div class="empty">课程库打开后，这里会显示当前课时的知识节点状态。</div>';
    renderLessonAdvance();
    return;
  }
  if (!cards.length) {
    els.atomProgressSummary.textContent = "当前课时暂无知识节点";
    els.atomStateList.innerHTML = '<div class="empty">生成知识节点后，这里会显示本节候选知识点。</div>';
    renderLessonAdvance();
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
  renderLessonAdvance();
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
  if (guardPublicDemoWrite("当前模式不允许重新生成知识节点。")) {
    return;
  }
  if (!state.courseId || !state.lectureId) {
    return;
  }
  await sendJson("/api/cards/generate", {
    course_id: state.courseId,
    lecture_id: state.lectureId,
    overwrite: true,
    compile_mode: "model",
    compile_provider: "deepseek",
    split_map_mode: true,
    fast_map_mode: true,
    fast_reduce_mode: true,
  });
  await loadCards();
  await loadCourseCards();
  setStatus("Knowledge cards generated");
}

function renderMarkdownUnavailable() {
  const course = selectedCourse();
  const lecture = selectedLecture();
  if (state.courseStoreLoading) {
    els.markdownNotes.innerHTML = `
      <article class="markdown-empty">
        <p class="item-title">正在读取课程笔记</p>
        <p class="item-meta">本地 SQLite 课程运行时正在打开。</p>
        <p>课程加载完成后，这里会显示当前课时的中文讲义、视觉证据和本地笔记。</p>
      </article>
    `;
    return;
  }
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

function markdownToHtml(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const html = [];
  let listOpen = false;
  const closeList = () => {
    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      html.push(`<h4>${escapeHtml(line.slice(4))}</h4>`);
      continue;
    }
    if (line.startsWith("## ")) {
      closeList();
      html.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
      continue;
    }
    if (line.startsWith("# ")) {
      closeList();
      html.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
      continue;
    }
    if (line.startsWith("- ")) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${escapeHtml(line.slice(2))}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${escapeHtml(line)}</p>`);
  }
  closeList();
  return html.join("");
}

function renderNotes(notes) {
  const generatedNotes = notes.filter((note) => String(note.note_id || "").startsWith("generated_note_"));
  const localNotes = notes.filter((note) => !String(note.note_id || "").startsWith("generated_note_"));
  if (generatedNotes.length) {
    const generated = generatedNotes[generatedNotes.length - 1];
    els.markdownNotes.innerHTML = `
      <article class="markdown-rendered">
        ${markdownToHtml(generated.body)}
        <p class="citation">${escapeHtml(generated.updated_at || generated.created_at)} / ${escapeHtml(generated.note_id)}</p>
      </article>
    `;
  } else {
    renderMarkdownUnavailable();
  }
  if (!notes.length) {
    els.notesList.innerHTML = '<div class="empty">当前课时还没有本地笔记。</div>';
    return;
  }
  if (!localNotes.length) {
    els.notesList.innerHTML = '<div class="empty">当前课时还没有手写笔记。</div>';
    return;
  }
  els.notesList.innerHTML = `
    <h3>手写笔记</h3>
    ${localNotes
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

function renderVisualEvidence(visuals) {
  const generated = (visuals || []).filter((visual) => String(visual.provenance || "").includes("generated_keyframe"));
  const existing = els.markdownNotes.querySelector(".visual-evidence-block");
  if (existing) {
    existing.remove();
  }
  if (!generated.length) {
    els.markdownNotes.insertAdjacentHTML(
      "beforeend",
      '<section class="visual-evidence-block"><h3>关键截图</h3><p class="empty">当前课时还没有真实视频关键帧。导入时没有可用视频媒体源时，这里会保持空白。</p></section>',
    );
    return;
  }
  els.markdownNotes.insertAdjacentHTML(
    "beforeend",
    `
      <section class="visual-evidence-block">
        <h3>关键截图</h3>
        <div class="visual-grid">
          ${generated
            .map(
              (visual) => `
                <figure class="visual-card">
                  <img src="/${escapeHtml(visual.image_path || "")}" alt="${escapeHtml(visual.title || "关键截图")}" />
                  <figcaption>
                    <strong>${escapeHtml(visual.title || visual.visual_id || "关键截图")}</strong>
                    <span>${escapeHtml(visual.explanation || visual.provenance || "")}</span>
                  </figcaption>
                </figure>
              `,
            )
            .join("")}
        </div>
      </section>
    `,
  );
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
  if (guardPublicDemoWrite("当前模式不允许保存本地笔记。")) {
    return;
  }
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
  if (guardPublicDemoWrite("当前模式不允许保存书签。")) {
    return;
  }
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
  if (guardPublicDemoWrite("当前模式不允许写入阅读进度。")) {
    return;
  }
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
  const turnId = state.chatTurnId + 1;
  state.chatTurnId = turnId;
  els.chatSendButton.disabled = true;
  appendChatBubble("user", message);
  els.chatInput.value = "";
  const assistantBubble = appendChatBubble("assistant", "");
  const eventsWrap = assistantBubble.querySelector(".chat-events");
  const bodyWrap = assistantBubble.querySelector(".chat-body");
  const waiting = createChatWaitingController(bodyWrap);
  waiting.show(
    "正在判断目前知识点状态",
    "Hermes 已收到问题，会先读取本节课知识原子，再决定从哪一口开始。",
    "routing",
  );
  setStatus("Chat is running");
  try {
    const events = [];
    let assistantText = "";
    const streamText = createTypewriterStream(bodyWrap);
    await postSseStream(
      "/api/chat/stream",
      {
        course_id: state.courseId,
        lecture_id: state.lectureId,
        lecture_sequence: state.lectureSequence,
        message,
        thread_id: state.chatThreadId,
        visitor_session_id: ensureVisitorSessionId(),
        channel: "web",
      },
      (event) => {
        events.push(event);
        const delta = event.data?.payload?.delta || "";
        if (event.event === "message_delta" && delta) {
          assistantText += delta;
          waiting.stop();
          streamText.push(delta);
          markAtomsFromText(delta);
          els.chatLog.scrollTop = els.chatLog.scrollHeight;
          return;
        }
        if (event.event === "tool_chain" && event.data?.payload) {
          appendToolChainEvent(eventsWrap, event.data.payload);
          updateChatWaitingFromTool(bodyWrap, event.data.payload, assistantText, waiting);
          return;
        }
        if (event.event === "teaching_state" && event.data?.payload) {
          renderHermesTeachingState(event.data.payload);
          if (!assistantText) {
            waiting.show(
              "正在判断目前知识点状态",
              "已读取课程状态，正在确认你现在卡在哪个知识原子。",
              "routing",
            );
          }
          return;
        }
        if (event.event === "runtime_metric" && event.data?.payload) {
          appendRuntimeMetricEvent(eventsWrap, event.data.payload);
          updateChatWaitingFromRuntimeMetric(bodyWrap, event.data.payload, assistantText, waiting);
          return;
        }
        if (event.event === "error" && event.data?.payload?.message && !assistantText) {
          waiting.stop();
          bodyWrap.innerHTML = `<p class="blocked">${escapeHtml(event.data.payload.message)}</p>`;
        }
      },
    );
    await streamText.done();
    renderChatEvents(events, { bodyWrap, eventsWrap, preserveBody: Boolean(assistantText) });
    const threadState = events.find((event) => event.event === "thread_state")?.data || {};
    state.chatThreadId = threadState.thread?.thread_id || state.chatThreadId;
    await refreshAfterChatTurn(turnId);
    setStatus("Chat ready");
  } catch (error) {
    waiting.stop();
    bodyWrap.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
    setStatus("Chat failed");
  } finally {
    waiting.stop();
    state.chatBusy = false;
    els.chatSendButton.disabled = false;
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }
}

async function refreshChatThreads() {
  if (!state.courseId) {
    return;
  }
  try {
    const payload = await getJson(
      `/api/chat/history?course_id=${encodeURIComponent(state.courseId)}&visitor_session_id=${encodeURIComponent(
        ensureVisitorSessionId(),
      )}`,
    );
    state.chatThreads = Array.isArray(payload.threads) ? payload.threads : [];
    if (!state.chatThreadId) {
      state.chatThreadId = payload.thread?.thread_id || "";
    }
    renderChatThreadSelect();
  } catch (_error) {
    // Chat history is support state; keep the live reply visible if refresh fails.
  }
}

async function refreshAfterChatTurn(turnId) {
  if (turnId !== state.chatTurnId) {
    return;
  }
  await Promise.allSettled([refreshChatThreads(), loadLearningState(), loadCards()]);
}

async function endVisitorSession({ silent = false } = {}) {
  if (!state.visitorSessionId) {
    resetVisitorSessionId();
    return;
  }
  const endedSessionId = state.visitorSessionId;
  try {
    await sendJson("/api/chat/session/end", {
      visitor_session_id: endedSessionId,
      course_id: state.courseId,
    });
  } catch (_error) {
    if (!silent) {
      setStatus("Load failed");
    }
  }
  resetVisitorSessionId();
  state.chatThreads = [];
  state.chatThreadId = "";
  state.currentHermesAtoms = [];
  els.chatLog.innerHTML = "";
  renderChatThreadSelect();
  renderChatEmptyState();
  renderAtomStates();
  if (!silent) {
    setStatus("本次体验已清空");
  }
}

function sendEndSessionBeacon() {
  if (!state.visitorSessionId) {
    return;
  }
  const payload = JSON.stringify({
    visitor_session_id: state.visitorSessionId,
    course_id: state.courseId,
  });
  if (navigator.sendBeacon) {
    navigator.sendBeacon("/api/chat/session/end", new Blob([payload], { type: "application/json" }));
  }
}

function createTypewriterStream(bodyWrap) {
  let fullText = "";
  let renderedCount = 0;
  let running = false;

  async function pump() {
    if (running) {
      return;
    }
    running = true;
    while (renderedCount < fullText.length) {
      renderedCount += Math.min(3, fullText.length - renderedCount);
      bodyWrap.innerHTML = `<p>${escapeHtml(fullText.slice(0, renderedCount))}<span class="stream-caret"></span></p>`;
      els.chatLog.scrollTop = els.chatLog.scrollHeight;
      await new Promise((resolve) => setTimeout(resolve, 16));
    }
    bodyWrap.innerHTML = `<p>${escapeHtml(fullText)}</p>`;
    running = false;
  }

  return {
    push(delta) {
      fullText += String(delta || "");
      pump();
    },
    async done() {
      while (running || renderedCount < fullText.length) {
        await new Promise((resolve) => setTimeout(resolve, 16));
      }
      if (fullText) {
        bodyWrap.innerHTML = `<p>${escapeHtml(fullText)}</p>`;
      }
    },
  };
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

async function postSseStream(url, payload, onEvent) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const rawError = await response.text();
    throw new Error(normalizeChatStreamError(response.status, rawError));
  }
  if (!response.body) {
    for (const event of parseSse(await response.text())) {
      onEvent(event);
    }
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) {
        onEvent(event);
      }
    }
  }
  buffer += decoder.decode();
  const event = parseSseBlock(buffer);
  if (event) {
    onEvent(event);
  }
}

function normalizeChatStreamError(status, rawError) {
  try {
    const payload = JSON.parse(rawError || "{}");
    if (status === 429) {
      return payload.error || "当前访客较多，请稍后再试。为了保证每个人的体验，演示环境限制了并发。";
    }
    return payload.error || `Request failed: ${status}`;
  } catch (_error) {
    if (status === 429) {
      return "当前访客较多，请稍后再试。为了保证每个人的体验，演示环境限制了并发。";
    }
    return rawError || `Request failed: ${status}`;
  }
}

function parseSse(text) {
  return text
    .trim()
    .split("\n\n")
    .filter(Boolean)
    .map(parseSseBlock)
    .filter(Boolean);
}

function parseSseBlock(block) {
  const cleaned = String(block || "").trim();
  if (!cleaned) {
    return null;
  }
  const event = { event: "message", id: "", data: {} };
  const dataLines = [];
  for (const line of cleaned.split("\n")) {
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

function renderChatEvents(events, { bodyWrap, eventsWrap, preserveBody = false }) {
  const messageEvent = events.find((event) => event.event === "message_delta");
  const errorEvent = events.find((event) => event.event === "error");
  const mediaEvents = events.filter((event) => event.event === "media");
  const teachingStateEvent = events.find((event) => event.event === "teaching_state");
  if (preserveBody) {
    // Incremental rendering already filled the assistant bubble.
  } else if (messageEvent?.data?.payload?.delta) {
    bodyWrap.innerHTML = `<p>${escapeHtml(messageEvent.data.payload.delta)}</p>`;
    markAtomsFromText(messageEvent.data.payload.delta);
  } else if (errorEvent?.data?.payload?.message) {
    bodyWrap.innerHTML = `<p class="blocked">${escapeHtml(errorEvent.data.payload.message)}</p>`;
  } else {
    bodyWrap.innerHTML = '<p class="blocked">Hermes gateway did not return a visible reply.</p>';
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
  if (teachingStateEvent?.data?.payload) {
    renderHermesTeachingState(teachingStateEvent.data.payload);
  }
  if (!eventsWrap.querySelector(".chat-event")) {
    eventsWrap.innerHTML = "";
  }
}

function renderPersistedTeachingControl(events) {
  const teachingEvent = [...events].reverse().find((event) => event.event_type === "teaching_control");
  const payload = teachingEvent?.payload || {};
  const visible = payload.student_visible || {};
  const signals = payload.mastery_signals || null;
  if (!visible.knowledge_atoms?.length && !signals) {
    return;
  }
  renderHermesTeachingState({
    status: "history",
    progress_ratio_label: payload.progress_ratio_label || "",
    next_step_label: visible.next_step_label || "",
    knowledge_atoms: visible.knowledge_atoms || [],
    learning_signals: normalizePersistedLearningSignals(signals),
  });
}

function eventsForMessage(events, message) {
  const messageId = String(message?.message_id || "");
  if (!messageId) {
    return [];
  }
  return events.filter((event) => String(event.message_id || "") === messageId);
}

function renderPersistedChatEvents(events, eventsWrap) {
  if (!eventsWrap) {
    return;
  }
  const toolChainEvents = events
    .map(normalizePersistedChatEvent)
    .filter((event) => event.event === "tool_chain" && event.data?.payload);
  if (!toolChainEvents.length) {
    return;
  }
  eventsWrap.innerHTML = "";
  for (const event of toolChainEvents) {
    appendToolChainEvent(eventsWrap, event.data.payload);
  }
}

function normalizePersistedChatEvent(event) {
  const payload = event?.payload || {};
  const sseEvent = payload.sse_event || "";
  if (sseEvent) {
    return {
      event: sseEvent,
      id: payload.sse_id || "",
      data: payload,
    };
  }
  return {
    event: event?.event_type || "",
    id: event?.event_id || "",
    data: { payload },
  };
}

function normalizePersistedLearningSignals(signals) {
  if (!signals) {
    return null;
  }
  return {
    retrieval_signal: Boolean(signals.retrieval),
    grounded_evidence_signal: Boolean(signals.evidence),
    causal_chain_signal: Boolean(signals.causal),
    boundary_signal: Boolean(signals.boundary),
    transfer_signal: Boolean(signals.transfer),
    scope_challenge_signal: Boolean(signals.scope_challenge),
    same_atom_probe_count: Number(signals.probe_count || 0),
    overquestioning_risk: Boolean(signals.overquestioning_risk),
  };
}

function appendToolChainEvent(eventsWrap, payload) {
  const label = payload.label || "Hermes 工具链";
  const status = payload.status || "运行中";
  const detail = payload.detail || "";
  const item = document.createElement("span");
  item.className = "chat-event is-tool_chain";
  item.title = detail;
  item.textContent = `${label} · ${status}`;
  eventsWrap.appendChild(item);
}

function appendRuntimeMetricEvent(eventsWrap, payload) {
  if (!eventsWrap || !payload || payload.stage !== "stream_done") {
    return;
  }
  const item = document.createElement("span");
  item.className = "chat-event is-runtime_metric";
  item.title = `prompt ${Number(payload.prompt_chars || 0)} chars`;
  item.textContent = `耗时 路由 ${formatMetricSeconds(payload.route_ms)} · 首字 ${formatMetricSeconds(payload.first_delta_ms)}`;
  eventsWrap.appendChild(item);
}

function updateChatWaitingFromTool(bodyWrap, payload, assistantText, waiting = null) {
  if (assistantText) {
    return;
  }
  const status = String(payload.status || "");
  if (status.includes("完成") || status.toLowerCase().includes("completed")) {
    setChatWaiting(
      bodyWrap,
      waiting,
      "知识点状态已判断完成，正在组织第一句话",
      "教学路由已经返回，接下来会开始流式输出。",
      "answering",
    );
    return;
  }
  setChatWaiting(
    bodyWrap,
    waiting,
    "正在判断目前知识点状态",
    "Hermes 正在真实调用 studio_office_teaching_route，不会跳过教学路由。",
    "routing",
  );
}

function updateChatWaitingFromRuntimeMetric(bodyWrap, payload, assistantText, waiting = null) {
  if (assistantText || !payload) {
    return;
  }
  if (payload.stage === "gateway_request_ready") {
    setChatWaiting(
      bodyWrap,
      waiting,
      "正在判断目前知识点状态",
      "请求已进入 Hermes，正在等待模型触发真实教学路由。",
      "routing",
    );
  }
  if (payload.stage === "route_tool_completed") {
    setChatWaiting(
      bodyWrap,
      waiting,
      "知识点状态已判断完成，正在组织第一句话",
      "Hermes 已拿到本轮教学位置，马上开始流式回复。",
      "answering",
    );
  }
}

function createChatWaitingController(bodyWrap) {
  let active = true;
  let phase = "routing";
  const timers = [
    setTimeout(() => {
      if (!active) {
        return;
      }
      if (phase === "answering") {
        renderChatWaitingState(
          bodyWrap,
          "Hermes 正在组织第一句话",
          "教学路由已完成，首字可能还需要几秒，不需要重复发送。",
        );
        return;
      }
      renderChatWaitingState(
        bodyWrap,
        "还在判断目前知识点状态",
        "通常需要 3-6 秒；系统会先确认教学位置，再把回复放出来。",
      );
    }, 6000),
    setTimeout(() => {
      if (!active) {
        return;
      }
      renderChatWaitingState(
        bodyWrap,
        "Hermes 还在处理，请再等一下",
        "这次请求仍在同一条链路里，无需重复发送你的问题。",
      );
    }, 12000),
  ];
  return {
    show(text, detail = "", nextPhase = phase) {
      if (!active) {
        return;
      }
      phase = nextPhase || phase;
      renderChatWaitingState(bodyWrap, text, detail);
    },
    stop() {
      active = false;
      for (const timer of timers) {
        clearTimeout(timer);
      }
    },
  };
}

function setChatWaiting(bodyWrap, waiting, text, detail = "", phase = "routing") {
  if (waiting) {
    waiting.show(text, detail, phase);
    return;
  }
  renderChatWaitingState(bodyWrap, text, detail);
}

function renderChatWaitingState(bodyWrap, text, detail = "") {
  if (!bodyWrap) {
    return;
  }
  bodyWrap.innerHTML = `
    <div class="chat-waiting">
      <span class="chat-waiting-dot" aria-hidden="true"></span>
      <div>
        <p>${escapeHtml(text)}</p>
        ${detail ? `<p class="chat-waiting-detail">${escapeHtml(detail)}</p>` : ""}
      </div>
    </div>
  `;
}

function formatMetricSeconds(value) {
  const ms = Number(value || 0);
  if (!Number.isFinite(ms) || ms <= 0) {
    return "-";
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

function renderHermesTeachingState(payload) {
  const atoms = Array.isArray(payload.knowledge_atoms) ? payload.knowledge_atoms : [];
  renderLearningSignals(payload.learning_signals || null);
  if (!atoms.length) {
    state.currentHermesAtoms = [];
    renderLessonAdvance();
    return;
  }
  state.currentHermesAtoms = atoms;
  const ratio = payload.progress_ratio_label ? ` · ${payload.progress_ratio_label}` : "";
  const stateLabel =
    payload.next_step_label ||
    (String(payload.status || "").startsWith("blocked") ? "等待课程接入" : "Hermes 正在带学");
  els.atomProgressSummary.textContent = `${stateLabel}${ratio}`;
  els.atomStateList.innerHTML = atoms
    .map(
      (atom) => {
        const atomClass = hermesAtomClass(atom);
        return `
        <article class="atom-item ${atomClass}">
          <div>
            <p class="atom-title">${escapeHtml(atom.label || "当前学习节点")}</p>
            <p class="citation">${escapeHtml(atom.focus || atom.state_hint || "等待你的回答")}</p>
          </div>
          <span class="atom-state">${escapeHtml(atom.status || "正在带学")}</span>
        </article>
      `;
      },
    )
    .join("");
  renderLessonAdvance();
}

function hasCompletedHermesAtoms() {
  const atoms = state.currentHermesAtoms || [];
  return Boolean(atoms.length) && atoms.every((atom) => hermesAtomClass(atom) === "is-passed");
}

function renderLessonAdvance() {
  if (!els.lessonAdvancePanel || !els.lessonAdvanceButton) {
    return;
  }
  const targetLecture = nextLecture();
  const canAdvance = hasCompletedHermesAtoms() && Boolean(targetLecture);
  els.lessonAdvancePanel.hidden = !canAdvance;
  els.lessonAdvanceButton.disabled = !canAdvance;
  if (targetLecture) {
    els.lessonAdvanceButton.textContent = `下一节课：${targetLecture.title || `第 ${targetLecture.sequence} 课`}`;
  } else {
    els.lessonAdvanceButton.textContent = "下一节课";
  }
}

async function advanceToNextLecture() {
  const targetLecture = nextLecture();
  if (!targetLecture || !hasCompletedHermesAtoms()) {
    return;
  }
  await selectLecture(targetLecture.sequence);
  setView("interaction");
  setStatus(`已进入第 ${targetLecture.sequence} 课`);
}

function renderLearningSignals(signals) {
  if (!els.learningSignalList) {
    return;
  }
  if (!signals) {
    els.learningSignalList.innerHTML = "";
    return;
  }
  const items = [
    ["retrieval_signal", "提取"],
    ["grounded_evidence_signal", "证据"],
    ["causal_chain_signal", "因果"],
    ["boundary_signal", "边界"],
    ["transfer_signal", "迁移"],
  ];
  els.learningSignalList.innerHTML = items
    .map(([key, label]) => {
      const active = Boolean(signals[key]);
      return `<span class="learning-signal ${active ? "is-on" : ""}">${label}</span>`;
    })
    .join("");
}

function hermesAtomClass(atom) {
  const hint = String(atom.state_hint || "").toLowerCase();
  const status = String(atom.status || "");
  if (hint === "passed" || status.includes("已通过")) {
    return "is-passed";
  }
  if (hint === "current" || hint === "exit_check" || status.includes("当前") || status.includes("收口")) {
    return "is-hermes";
  }
  return "is-waiting";
}

function renderChatEmptyState() {
  if (!els.chatLog || els.chatLog.querySelector(".chat-message")) {
    return;
  }
  if (state.courseStoreLoading) {
    const useDemoCopy = shouldUsePublicDemoLoadingCopy();
    els.chatLog.innerHTML = `
      <div class="empty">
        <p>${escapeHtml(useDemoCopy ? publicDemoLoadingCopy : "正在连接本地课程库，课程和课时准备好后可以直接开始学习。")}</p>
        <p class="citation">${escapeHtml(
          useDemoCopy ? "示例课程准备好后，可以直接向学习助手提问。" : "稍后可直接输入：开始学习当前课程。",
        )}</p>
      </div>
    `;
    return;
  }
  if (isPublicDemo()) {
    els.chatLog.innerHTML = `
      <div class="empty">
        <p>示例课程已准备好，可以直接和学习助手对话。</p>
        <p class="citation">试试：我想理解 cache 的局部性，能带我开始吗？</p>
      </div>
    `;
    return;
  }
  els.chatLog.innerHTML = `
    <div class="empty">
      <p>导入或选择任意 B 站课程后，这里会接入 Hermes 教学前台，围绕当前课程带你一步一步学。</p>
      <p class="citation">试试：开始学习当前课程 / 这节课我应该先理解什么？</p>
    </div>
  `;
}

els.importButton.addEventListener("click", importCollection);
els.pasteCookieButton?.addEventListener("click", pasteBilibiliCookieFromClipboard);
els.qrLoginButton?.addEventListener("click", startBilibiliQrLogin);
els.clearQrLoginButton?.addEventListener("click", clearBilibiliQrLogin);
els.clearCookieButton?.addEventListener("click", clearBilibiliCookieInput);
els.clearStoredCookieButton?.addEventListener("click", () => {
  clearStoredBilibiliCookie().catch((error) => {
    els.importReceipt.innerHTML = `<p class="blocked">${escapeHtml(error.message)}</p>`;
  });
});
els.refreshButton.addEventListener("click", loadCourses);
els.chatSendButton.addEventListener("click", runChat);
els.endSessionButton?.addEventListener("click", () => {
  endVisitorSession().catch((error) => {
    els.chatLog.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    setStatus("Load failed");
  });
});
els.lessonAdvanceButton.addEventListener("click", () => {
  advanceToNextLecture().catch((error) => {
    setStatus("Load failed");
    els.chatLog.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  });
});
els.chatThreadSelect.addEventListener("change", () => {
  if (!els.chatThreadSelect.value) {
    state.chatThreadId = "";
    els.chatLog.innerHTML = "";
    renderChatEmptyState();
    return;
  }
  const thread = state.chatThreads[Number(els.chatThreadSelect.value || 0)];
  if (thread?.thread_id && thread.thread_id !== state.chatThreadId) {
    loadChatHistory(thread.thread_id).catch((error) => {
      els.chatLog.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      setStatus("Load failed");
    });
  }
});
els.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
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
window.addEventListener("pagehide", sendEndSessionBeacon);

ensureVisitorSessionId();
setView("interaction");
renderCourseLoadingState();
setCourseLoadingStatus();

loadRuntimeMode()
  .then(async () => {
    if (!isPublicDemo()) {
      await loadBilibiliCookieStatus();
    }
    await loadCourses();
    if (!isPublicDemo()) {
      await restoreLatestImportStatus();
    }
  })
  .catch((error) => {
    els.segments.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    setStatus("Load failed");
  });
