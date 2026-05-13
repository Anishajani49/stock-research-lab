document.addEventListener('DOMContentLoaded', () => {
  const scrollRoot = document.getElementById('neo-scroll');
  if (!scrollRoot) return;

  const progressFill = document.getElementById('neo-progress-fill');
  const riverScene = document.querySelector('[data-river-scene]');
  const riverTrack = document.getElementById('neo-river-track');
  const floaters = Array.from(document.querySelectorAll('.neo-float'));
  const steps = Array.from(document.querySelectorAll('.neo-step'));
  const meterFill = document.getElementById('neo-meter-fill');
  const meterText = document.getElementById('neo-meter-text');
  const sceneEls = Array.from(document.querySelectorAll('[data-scene]'));

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  const sceneProgress = (el) => {
    const r = el.getBoundingClientRect();
    const vh = window.innerHeight;
    const total = r.height + vh;
    const seen = vh - r.top;
    return clamp(seen / total, 0, 1);
  };

  const setActiveStepFromScroll = () => {
    if (!steps.length) return;
    let best = steps[0];
    let bestRatio = 0;
    steps.forEach((s) => {
      const rect = s.getBoundingClientRect();
      const vh = window.innerHeight;
      const visible = Math.max(0, Math.min(rect.bottom, vh) - Math.max(rect.top, 0));
      const ratio = visible / Math.max(1, rect.height);
      if (ratio > bestRatio) {
        bestRatio = ratio;
        best = s;
      }
    });
    steps.forEach((s) => s.classList.toggle('is-active', s === best));
    const step = Number(best.dataset.step || 1);
    const pct = Math.round((step / steps.length) * 100);
    if (meterFill) meterFill.style.width = `${pct}%`;
    if (meterText) meterText.textContent = `Step ${step} / ${steps.length} · ${best.dataset.stepTitle || ''}`;
  };

  const render = () => {
    const maxScroll = Math.max(1, scrollRoot.scrollHeight - scrollRoot.clientHeight);
    const globalProgress = clamp(scrollRoot.scrollTop / maxScroll, 0, 1);
    if (progressFill) progressFill.style.width = `${globalProgress * 100}%`;

    // Scroll-reactive parallax depth
    floaters.forEach((el) => {
      const depth = Number(el.dataset.depth || 10);
      const shift = (globalProgress - 0.5) * depth * 2;
      el.style.setProperty('--depth-shift', `${shift.toFixed(2)}px`);
    });

    // Horizontal river driven by scene-local progress
    if (riverScene && riverTrack) {
      const p = sceneProgress(riverScene);
      const shift = -p * 700;
      riverTrack.style.setProperty('--river-shift', `${shift.toFixed(2)}px`);
    }

    setActiveStepFromScroll();

    // Subtle scene emphasis
    sceneEls.forEach((scene) => {
      const p = sceneProgress(scene);
      const alpha = 0.62 + (p * 0.38);
      scene.style.opacity = String(clamp(alpha, 0.62, 1));
    });
  };

  let raf = 0;
  const tick = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      render();
    });
  };

  scrollRoot.addEventListener('scroll', tick, { passive: true });
  window.addEventListener('resize', tick);
  render();
});
