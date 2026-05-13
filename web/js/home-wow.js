document.addEventListener('DOMContentLoaded', () => {
  initProgressBar();
  initReveal();
  initTheater();
});

function initProgressBar() {
  const fill = document.getElementById('atelier-progress-fill');
  if (!fill) return;
  const update = () => {
    const h = document.documentElement;
    const max = Math.max(1, h.scrollHeight - h.clientHeight);
    const pct = Math.min(100, Math.max(0, (h.scrollTop / max) * 100));
    fill.style.width = `${pct}%`;
  };
  window.addEventListener('scroll', update, { passive: true });
  update();
}

function initReveal() {
  const nodes = Array.from(document.querySelectorAll('[data-reveal]'));
  if (!nodes.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add('is-visible');
    });
  }, { threshold: 0.18 });
  nodes.forEach((n) => obs.observe(n));
}

function initTheater() {
  const steps = Array.from(document.querySelectorAll('[data-step]'));
  if (!steps.length) return;

  const stageTitle = document.getElementById('stage-title');
  const stageBody = document.getElementById('stage-body');
  const meterFill = document.getElementById('stage-meter-fill');
  const meterText = document.getElementById('stage-meter-text');

  const setActive = (el) => {
    steps.forEach((s) => s.classList.toggle('is-active', s === el));
    const idx = steps.indexOf(el) + 1;
    const total = steps.length;
    const pct = Math.round((idx / total) * 100);
    if (stageTitle) stageTitle.textContent = el.dataset.title || '';
    if (stageBody) stageBody.textContent = el.dataset.body || '';
    if (meterFill) {
      meterFill.style.width = `${pct}%`;
      if (el.dataset.color) meterFill.style.background =
        `linear-gradient(90deg, ${el.dataset.color}, var(--tone-sun), var(--tone-teal))`;
    }
    if (meterText) meterText.textContent = `Step ${idx} / ${total}`;
  };

  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (visible[0]) setActive(visible[0].target);
  }, {
    threshold: [0.25, 0.45, 0.65],
    rootMargin: '-18% 0px -32% 0px',
  });

  steps.forEach((s) => observer.observe(s));
  setActive(steps[0]);
}
