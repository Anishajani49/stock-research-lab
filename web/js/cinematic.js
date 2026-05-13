// =====================================================================
// Cinematic — shared motion primitives.
// Drop these in on any page; they hook on data-attributes so they don't
// fight with page-specific scripts.
// =====================================================================

(function () {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.addEventListener('DOMContentLoaded', () => {
    initNavScroll();
    initProgressBar();
    initReveal();
    initParallax();
    initStickyScale();
    initHorizontalPin();
    initMagneticSearch();
    initCountUp();
  });

  // -------------------------------------------------------------------
  // Nav: add `.is-scrolled` once we leave the top of the page
  // -------------------------------------------------------------------
  function initNavScroll() {
    const nav = document.querySelector('nav.nav');
    if (!nav) return;
    const update = () => nav.classList.toggle('is-scrolled', window.scrollY > 8);
    update();
    window.addEventListener('scroll', update, { passive: true });
  }

  // -------------------------------------------------------------------
  // Top progress bar — auto-mounts if `.cin-progress` not in DOM
  // -------------------------------------------------------------------
  function initProgressBar() {
    let bar = document.querySelector('.cin-progress > i');
    if (!bar) {
      const root = document.createElement('div');
      root.className = 'cin-progress';
      const i = document.createElement('i');
      root.appendChild(i);
      document.body.appendChild(root);
      bar = i;
    }
    const update = () => {
      const h = document.documentElement;
      const max = Math.max(1, h.scrollHeight - h.clientHeight);
      const pct = Math.min(100, Math.max(0, (h.scrollTop / max) * 100));
      bar.style.width = pct + '%';
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
  }

  // -------------------------------------------------------------------
  // Reveal-on-scroll (data-cin-reveal)
  // Children of [data-cin-stagger] inherit transition-delay from CSS.
  // -------------------------------------------------------------------
  function initReveal() {
    const nodes = document.querySelectorAll('[data-cin-reveal]');
    if (!nodes.length) return;
    if (reduced) {
      nodes.forEach((n) => n.classList.add('is-in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -8% 0px' });
    nodes.forEach((n) => io.observe(n));
  }

  // -------------------------------------------------------------------
  // Parallax — elements with [data-cin-parallax="0.4"] (speed factor)
  // moved on rAF. translate3d only — never width/height.
  // -------------------------------------------------------------------
  function initParallax() {
    if (reduced) return;
    const nodes = Array.from(document.querySelectorAll('[data-cin-parallax]'));
    if (!nodes.length) return;

    const items = nodes.map((el) => ({
      el,
      speed: parseFloat(el.dataset.cinParallax) || 0.2,
      axis: el.dataset.cinParallaxAxis || 'y',
    }));

    let ticking = false;
    const apply = () => {
      const y = window.scrollY;
      items.forEach(({ el, speed, axis }) => {
        const rect = el.getBoundingClientRect();
        const center = window.innerHeight / 2 - (rect.top + rect.height / 2);
        const offset = center * speed * -0.6; // -0.6 -> nicer perceived range
        el.style.transform = axis === 'x'
          ? `translate3d(${offset}px, 0, 0)`
          : `translate3d(0, ${offset}px, 0)`;
      });
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        requestAnimationFrame(apply);
        ticking = true;
      }
    };
    apply();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
  }

  // -------------------------------------------------------------------
  // Sticky-scale — outer wrapper `.cin-sticky-scale`, target `.cin-sticky-target`.
  // As the wrapper scrolls through the viewport, scales the target 1 -> 1.7.
  // -------------------------------------------------------------------
  function initStickyScale() {
    const wraps = document.querySelectorAll('.cin-sticky-scale');
    if (!wraps.length) return;
    if (reduced) {
      wraps.forEach((w) => {
        const t = w.querySelector('.cin-sticky-target');
        if (t) t.style.transform = 'scale(1.1)';
      });
      return;
    }
    let ticking = false;
    const apply = () => {
      wraps.forEach((w) => {
        const target = w.querySelector('.cin-sticky-target');
        if (!target) return;
        const rect = w.getBoundingClientRect();
        const total = rect.height - window.innerHeight;
        const progress = Math.min(1, Math.max(0, -rect.top / Math.max(1, total)));
        const scale = 1 + progress * 0.7;       // 1.0 -> 1.7
        const opacity = 1 - progress * 0.15;    // subtle fade at the end
        const lift = -progress * 24;            // lifts as it grows
        target.style.transform = `translate3d(0, ${lift}px, 0) scale(${scale.toFixed(3)})`;
        target.style.opacity = opacity.toFixed(3);
      });
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        requestAnimationFrame(apply);
        ticking = true;
      }
    };
    apply();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
  }

  // -------------------------------------------------------------------
  // Horizontal pin — `.cin-pin` is a tall wrapper whose `.cin-pin-stage`
  // sticks to the viewport. As the user scrolls vertically through the
  // wrapper, `.cin-pin-track` translates horizontally so the panels
  // sweep across like a filmstrip. Cinematic.
  // -------------------------------------------------------------------
  function initHorizontalPin() {
    const wraps = document.querySelectorAll('.cin-pin');
    if (!wraps.length) return;

    const instances = Array.from(wraps).map((w) => {
      const track = w.querySelector('.cin-pin-track');
      const panels = w.querySelectorAll('.cin-pin-panel');
      const progress = w.querySelectorAll('.cin-pin-progress > i');
      return { w, track, panels, progress };
    });

    if (reduced) {
      instances.forEach(({ w }) => { w.style.height = 'auto'; });
      return;
    }

    let ticking = false;
    const apply = () => {
      instances.forEach(({ w, track, panels, progress }) => {
        if (!track || !panels.length) return;
        const rect = w.getBoundingClientRect();
        const total = rect.height - window.innerHeight;
        const p = Math.min(1, Math.max(0, -rect.top / Math.max(1, total)));
        const maxOffset = (panels.length - 1) * window.innerWidth;
        track.style.transform = `translate3d(${-(p * maxOffset).toFixed(1)}px, 0, 0)`;
        // mark active panel
        const idx = Math.min(panels.length - 1, Math.round(p * (panels.length - 1)));
        progress.forEach((dot, i) => dot.classList.toggle('is-active', i <= idx));
      });
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        requestAnimationFrame(apply);
        ticking = true;
      }
    };
    apply();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
  }

  // -------------------------------------------------------------------
  // Magnetic search — add `is-focused` class to `.cin-search` when
  // an input inside is focused. Pure aesthetic.
  // -------------------------------------------------------------------
  function initMagneticSearch() {
    document.querySelectorAll('.cin-search').forEach((box) => {
      const input = box.querySelector('input');
      if (!input) return;
      input.addEventListener('focus', () => box.classList.add('is-focused'));
      input.addEventListener('blur',  () => box.classList.remove('is-focused'));
    });
  }

  // -------------------------------------------------------------------
  // Count-up — any element with [data-cin-count="123.4"] tweens to that
  // value when it enters the viewport.
  // -------------------------------------------------------------------
  function initCountUp() {
    const nodes = document.querySelectorAll('[data-cin-count]');
    if (!nodes.length) return;
    if (reduced) {
      nodes.forEach((n) => n.textContent = n.dataset.cinCount);
      return;
    }
    const tween = (el) => {
      const end = parseFloat(el.dataset.cinCount) || 0;
      const prefix = el.dataset.cinPrefix || '';
      const suffix = el.dataset.cinSuffix || '';
      const digits = parseInt(el.dataset.cinDigits || '0', 10);
      const dur = 1100;
      const start = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        const v = end * eased;
        el.textContent = prefix + v.toLocaleString('en-IN', {
          maximumFractionDigits: digits,
          minimumFractionDigits: digits,
        }) + suffix;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { tween(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.4 });
    nodes.forEach((n) => io.observe(n));
  }

  // Expose for page scripts that want to re-trigger after dynamic content
  window.Cinematic = {
    rescanReveal: initReveal,
    rescanCount:  initCountUp,
  };
})();
