// =====================================================================
// Home — page-specific behavior:
//   1. Procedurally render the candle field behind the hero
//   2. Drive the five-act journey "stage" panel as cards scroll into view
// =====================================================================

(function () {
  document.addEventListener('DOMContentLoaded', () => {
    paintCandleField();
    initJourneyStage();
  });

  // -------------------------------------------------------------------
  // Candle field — generates ~38 candles with deterministic random walk
  // -------------------------------------------------------------------
  function paintCandleField() {
    const g = document.getElementById('cin-candle-field');
    if (!g) return;
    const N = 38;
    const baseY = 320, range = 220, w = 1600;
    const step = w / (N + 1);
    let price = baseY;
    const seed = 7; // deterministic feel; not Math.random()
    let r = seed;
    const rand = () => {
      r = (r * 9301 + 49297) % 233280;
      return r / 233280;
    };
    const candles = [];
    for (let i = 0; i < N; i++) {
      const open  = price;
      const drift = (rand() - 0.5) * 60;
      const close = Math.max(120, Math.min(520, price + drift));
      const high  = Math.min(540, Math.max(open, close) + rand() * 30);
      const low   = Math.max(80,  Math.min(open, close) - rand() * 30);
      const up    = close <= open; // SVG y inverted: smaller y = higher price
      price = close;
      const x = step * (i + 1);
      candles.push({ x, open, close, high, low, up });
    }
    const cw = 11;
    g.innerHTML = candles.map((c) => {
      const top = Math.min(c.open, c.close);
      const bot = Math.max(c.open, c.close);
      const fill = c.up ? 'url(#cg-up)' : 'url(#cg-dn)';
      const stroke = c.up ? '#10b981' : '#f43f5e';
      return `
        <line x1="${c.x}" y1="${c.high}" x2="${c.x}" y2="${c.low}" stroke="${stroke}" stroke-opacity=".35"/>
        <rect x="${c.x - cw / 2}" y="${top}" width="${cw}" height="${Math.max(2, bot - top)}"
              fill="${fill}" stroke="${stroke}" stroke-opacity=".6"/>`;
    }).join('');
  }

  // -------------------------------------------------------------------
  // Journey stage controller — five .cin-act cards drive the right rail
  // -------------------------------------------------------------------
  function initJourneyStage() {
    const acts  = Array.from(document.querySelectorAll('[data-act]'));
    if (!acts.length) return;
    const title = document.getElementById('cin-stage-title');
    const body  = document.getElementById('cin-stage-body');
    const fill  = document.getElementById('cin-stage-fill');
    const text  = document.getElementById('cin-stage-text');

    const tone = {
      coral:  ['var(--acc-coral)',  'var(--acc-sun)'],
      sun:    ['var(--acc-sun)',    'var(--acc-coral)'],
      teal:   ['var(--acc-teal)',   'var(--acc-mint)'],
      blue:   ['var(--acc-blue)',   'var(--acc-indigo)'],
      indigo: ['var(--acc-indigo)', 'var(--acc-blue)'],
    };

    const setActive = (el) => {
      acts.forEach((a) => a.classList.toggle('is-active', a === el));
      const idx = acts.indexOf(el) + 1;
      const pct = Math.round((idx / acts.length) * 100);
      if (title) title.textContent = el.dataset.title || '';
      if (body)  body.textContent  = el.dataset.body  || '';
      if (fill) {
        fill.style.width = pct + '%';
        const [a, b] = tone[el.dataset.tone] || tone.indigo;
        fill.style.background = `linear-gradient(90deg, ${a}, ${b})`;
      }
      if (text) text.textContent = `Act ${idx} / ${acts.length}`;
    };

    // Click to jump
    acts.forEach((a) => a.addEventListener('click', () => setActive(a)));

    // Drive by scroll position — whichever act is most-visible wins
    const io = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]) setActive(visible[0].target);
    }, {
      threshold: [0.3, 0.55, 0.8],
      rootMargin: '-20% 0px -35% 0px',
    });
    acts.forEach((a) => io.observe(a));
    setActive(acts[0]);
  }
})();
