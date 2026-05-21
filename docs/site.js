(function () {
  const links = Array.from(document.querySelectorAll(".toc a"));
  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!sections.length) {
    return;
  }

  const byId = new Map(links.map((link) => [link.getAttribute("href").slice(1), link]));

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (!visible) {
        return;
      }

      links.forEach((link) => link.classList.remove("is-active"));
      const active = byId.get(visible.target.id);
      if (active) {
        active.classList.add("is-active");
      }
    },
    {
      rootMargin: "-18% 0px -70% 0px",
      threshold: [0.08, 0.2, 0.4],
    },
  );

  sections.forEach((section) => observer.observe(section));
})();
