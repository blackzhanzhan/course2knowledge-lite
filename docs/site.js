(function () {
  const english = {
    "nav.system": "System",
    "nav.demo": "Demo",
    "nav.walkthrough": "Flow",
    "nav.frontdesks": "Frontdesks",
    "nav.evidence": "Case",
    "nav.dossier": "Docs",
    "nav.deploy": "Deploy",
    "hero.kicker": "Showcase + technical dossier",
    "hero.title": "Do not leave knowledge inside the player.",
    "hero.lead":
      "Course2Knowledge Lite turns a Bilibili collection into transcript evidence, a local course knowledge store, and two frontdesks: Web for inspection, Feishu/Hermes for conversation.",
    "metric.lectures": "expanded lectures",
    "metric.segments": "transcript segments",
    "metric.frontdesks": "frontdesk entries",
    "metric.shots": "real case shots",
    "slice.source": "Source",
    "slice.evidence": "Evidence layer",
    "slice.kernel": "Shared base",
    "slice.web": "Read / search / annotate",
    "slice.feishu": "Ask / lookup / cite",
    "hero.webShot":
      "SHOT-01 Web Lite overview. A real local run showing reading, search, Q&A, notes, bookmarks, and progress.",
    "hero.dualShot":
      "SHOT-03 dual-frontdesk boundary. The Web side is a real frontend capture; Hermes is public profile/tool smoke evidence, not a production chat export.",
    "demo.kicker": "Public demo video",
    "demo.title":
      "In eighty seconds: import, evidence, Q&A, and dual frontdesks.",
    "demo.lead":
      "This video is cut from real public-child-repo screenshots and local run assets: collection import, lecture expansion, transcript evidence, Web reading, cited Q&A, knowledge cards, and Hermes Lite smoke all come from the same public case.",
    "demo.videoFallback": "Open the demo video",
    "demo.railLabel": "Video evidence",
    "demo.fact.duration":
      "Short silent cut for the GitHub Pages homepage, placed after the system view.",
    "demo.fact.assets":
      "Covers import, store, reader, search, Q&A, cards, notes, bookmarks, progress, Hermes smoke, and visual evidence.",
    "demo.fact.private":
      "Contains no private runtime evidence, production chat capture, private logs, or personal study positioning.",
    "walk.kicker": "Real case flow",
    "walk.title": "From one collection URL to two usable learning entries.",
    "walk.lead":
      "This case follows one Bilibili collection through the public import boundary, transcript evidence, course store, Web frontend, and Hermes frontend proof. The page shows the actual run, not a concept diagram.",
    "step.import.title": "Import collection",
    "step.import.body": "Use a Bilibili season URL as the public import boundary.",
    "step.expand.title": "Expand lectures",
    "step.expand.body":
      "Record ordered lectures with titles, BV/source URLs, and an import receipt.",
    "step.evidence.title": "Preserve evidence",
    "step.evidence.body":
      "Treat timestamped transcript segments as citeable learning evidence.",
    "step.store.title": "Build course store",
    "step.store.body":
      "Persist course, lecture, segment, card, note, bookmark, and progress records.",
    "step.web.title": "Read on Web",
    "step.web.body":
      "Read, search, ask, generate cards, and record state in Web Lite.",
    "step.feishu.title": "Hermes frontend",
    "step.feishu.body":
      "Use the public Hermes profile to prove the same tool boundary can be called by a conversational frontend.",
    "front.kicker": "One Store, Two Frontdesks",
    "front.title": "Web makes the evidence inspectable; Feishu/Hermes makes it askable.",
    "front.webLabel": "Inspectable reading workspace",
    "front.webCaption":
      "SHOT-08 reader detail: one transcript-backed lecture is opened with segment IDs and timestamps visible.",
    "front.web1": "Read transcript evidence by lecture.",
    "front.web2": "Search and Q&A both surface citations.",
    "front.web3":
      "Notes, bookmarks, and progress all land in the same local course store.",
    "front.chatLabel": "Conversational learning entry",
    "front.chatCaption":
      "SHOT-15 Hermes smoke: the public profile and 22 tool registrations pass. A real Feishu chat shot still needs a safe capture.",
    "front.chat1":
      "It does not duplicate chat memory; it reads the same course store.",
    "front.chat2":
      "The tool layer supports course lookup, search, Q&A, notes, bookmarks, progress, and visual evidence replies.",
    "front.chat3":
      "The public site currently shows safe smoke evidence, without exposing production chat identity.",
    "evidence.kicker": "Real case shots",
    "evidence.title": "16 evidence captures turn the chain from explainable into visible.",
    "evidence.lead":
      "These images come from the actual Web Lite, API bundle, local store, visual evidence, and Hermes profile smoke run. The chat gap is labelled honestly instead of being replaced by a private production screenshot.",
    "shot.01.title": "Web overview",
    "shot.01.body":
      "A real Web Lite page with course, reader, search, Q&A, notes, bookmarks, and progress.",
    "shot.03.title": "Dual-frontdesk boundary",
    "shot.03.body":
      "Web frontend capture plus Hermes smoke evidence, proving two entries over the same course store.",
    "shot.04.title": "Import receipt",
    "shot.04.body":
      "The public Lite import boundary accepts the Bilibili collection URL.",
    "shot.05.title": "Lecture expansion",
    "shot.05.body":
      "Thirty lectures are expanded with source IDs, titles, and URLs.",
    "shot.06.title": "Course store files",
    "shot.06.body":
      "A local SQLite course store supports both Web and Hermes tool layers.",
    "shot.07.title": "Transcript evidence",
    "shot.07.body":
      "Timestamped transcript segments keep stable segment IDs.",
    "shot.08.title": "Reader detail",
    "shot.08.body":
      "The Web reader opens one transcript-backed lecture.",
    "shot.09.title": "Search hit",
    "shot.09.body":
      "The RAG Agent query returns five transcript evidence hits.",
    "shot.10.title": "Cited Q&A",
    "shot.10.body":
      "Q&A returns an answered state with five citations.",
    "shot.11.title": "Knowledge cards",
    "shot.11.body":
      "Cards are generated from transcript segments and keep source segment IDs.",
    "shot.12.title": "Notes state",
    "shot.12.body":
      "A note is tied to the course and lecture in the Lite local store.",
    "shot.13.title": "Bookmarks state",
    "shot.13.body": "A bookmark points to a segment or card target.",
    "shot.14.title": "Reading progress",
    "shot.14.body":
      "Reading progress is written and readable through Web/API surfaces.",
    "shot.15.title": "Hermes smoke",
    "shot.15.body":
      "Public profile sync/smoke passes with 22 registered tools.",
    "shot.17.title": "Visual evidence reply",
    "shot.17.body":
      "Hermes Lite selects a public course image, explains it, and returns exactly one MEDIA path.",
    "shot.16.title": "Mobile Web",
    "shot.16.body": "The same course store remains readable on mobile.",
    "status.real": "real",
    "status.safe": "safe proof",
    "gallery.01": "SHOT-01 Web overview",
    "gallery.03": "SHOT-03 dual-frontdesk boundary",
    "gallery.04": "SHOT-04 import receipt",
    "gallery.05": "SHOT-05 lecture expansion",
    "gallery.06": "SHOT-06 course store files",
    "gallery.07": "SHOT-07 transcript evidence",
    "gallery.08": "SHOT-08 reader detail",
    "gallery.09": "SHOT-09 search hit",
    "gallery.10": "SHOT-10 cited Q&A",
    "gallery.11": "SHOT-11 knowledge cards",
    "gallery.12": "SHOT-12 notes state",
    "gallery.13": "SHOT-13 bookmarks state",
    "gallery.14": "SHOT-14 reading progress",
    "gallery.15": "SHOT-15 Hermes smoke",
    "gallery.17": "SHOT-17 visual evidence reply",
    "gallery.16": "SHOT-16 mobile Web",
    "thought.kicker": "Product thought",
    "thought.title":
      "Courses do not lack content; their content is locked in the timeline.",
    "thought.body":
      "Course2Knowledge Lite splits the player timeline into citeable evidence, organizes that evidence into a course knowledge store, then lets learners enter the same knowledge space through Web and Feishu/Hermes.",
    "thought.stack1": "Timeline",
    "thought.stack2": "Evidence",
    "thought.stack3": "Knowledge Store",
    "thought.stack4": "Inspectable Web",
    "thought.stack5": "Conversational Feishu",
    "boundary.kicker": "Public boundary",
    "boundary.title": "The loop is trimmed; the product is not a toy.",
    "boundary.lead":
      "The public version keeps the course-to-knowledge mainline while removing private planning, feedback, exercise, and production-identity capabilities.",
    "boundary.included": "Lite keeps",
    "boundary.in1": "Bilibili course import boundary",
    "boundary.in2": "Transcript evidence and local course store",
    "boundary.in3": "Lecture reader, search, citation Q&A",
    "boundary.in4": "Knowledge cards from source segments",
    "boundary.in5": "Notes, bookmarks, and reading progress",
    "boundary.in6": "Web Lite and Feishu/Hermes Lite frontdesks",
    "boundary.removed": "Public version removes",
    "boundary.out1": "Private planning layer",
    "boundary.out2": "Exercise feedback and visual exercise interpretation",
    "boundary.out3": "Learner scoring and mastery mutation loops",
    "boundary.out4": "Private orchestration and production identifiers",
    "boundary.out5": "Production chat exports and personal study logs",
    "boundary.out6": "Protected closed-loop automation",
    "dossier.kicker": "Technical dossier",
    "dossier.title": "The showcase site is also the engineering document entry.",
    "doc.demoVideo": "Script, storyboard, and acceptance rules",
    "doc.demoPrivacy": "Public media privacy boundary",
    "doc.boundary": "Public boundary and trimming rationale",
    "doc.arch": "Module boundaries and runtime flow",
    "doc.data": "Course, Lecture, Segment, Card, and state",
    "doc.import": "Collection expansion and import handoff",
    "doc.web": "Inspectable reading workspace",
    "doc.feishu": "Conversational frontend and Hermes profile",
    "doc.testing": "Boundary tests, smoke, and case evidence",
    "doc.deploy": "Local install and profile sync",
    "deploy.kicker": "Local deployment",
    "deploy.title":
      "The deployment path stays short because the work should be easy to inspect.",
    "footer.siteMap": "Site map",
    "footer.shotList": "Shot list",
    "footer.deployment": "Deployment",
    "footer.testing": "Testing",
  };

  const elements = Array.from(document.querySelectorAll("[data-i18n]"));
  const zh = new Map(
    elements.map((element) => [element.dataset.i18n, element.textContent.trim()])
  );
  const buttons = Array.from(document.querySelectorAll(".language-switcher [data-lang]"));

  function applyLanguage(lang) {
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    document.body.dataset.lang = lang === "en" ? "en" : "zh";

    for (const element of elements) {
      const key = element.dataset.i18n;
      const text = lang === "en" ? english[key] : zh.get(key);
      if (text) {
        element.textContent = text;
      }
    }

    for (const button of buttons) {
      const active = button.dataset.lang === lang;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    }

  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => applyLanguage(button.dataset.lang));
  });

  applyLanguage("zh");
})();
