document.addEventListener('DOMContentLoaded', () => {
  initScrollProgress();
  initRevealObserver();
  initStoryScroller();
});

function initScrollProgress() {
  const fill = document.getElementById('wow-progress-fill');
  if (!fill) return;
  const onScroll = () => {
    const h = document.documentElement;
    const max = Math.max(1, h.scrollHeight - h.clientHeight);
    const p = Math.min(100, Math.max(0, (h.scrollTop / max) * 100));
    fill.style.width = `${p}%`;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

function initRevealObserver() {
  const items = Array.from(document.querySelectorAll('[data-reveal]'));
  if (!items.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      }
    });
  }, { threshold: 0.16 });
  items.forEach((el) => obs.observe(el));
}

function initStoryScroller() {
  const chapters = Array.from(document.querySelectorAll('.story-chapter'));
  if (!chapters.length) return;

  const tag = document.getElementById('visual-tag');
  const title = document.getElementById('visual-title');
  const body = document.getElementById('visual-body');
  const meter = document.getElementById('visual-meter-fill');
  const meterLabel = document.getElementById('visual-meter-label');

  const setActive = (el) => {
    chapters.forEach((c) => c.classList.toggle('is-active', c === el));
    const tagText = el.dataset.visualTag || '';
    const titleText = el.dataset.visualTitle || '';
    const bodyText = el.dataset.visualBody || '';
    const meterPct = Number(el.dataset.visualMeter || 0);

    if (tag) tag.textContent = tagText;
    if (title) title.textContent = titleText;
    if (body) body.textContent = bodyText;
    if (meter) meter.style.width = `${meterPct}%`;
    if (meterLabel) meterLabel.textContent = `Learning Progress ${meterPct}%`;
  };

  const obs = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (visible[0]) setActive(visible[0].target);
  }, {
    threshold: [0.2, 0.4, 0.6, 0.8],
    rootMargin: '-10% 0px -30% 0px',
  });

  chapters.forEach((ch) => obs.observe(ch));
  setActive(chapters[0]);
}
