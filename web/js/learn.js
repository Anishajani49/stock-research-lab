// Candlestick learning page — pattern gallery + interactive detail panel.

const PATTERNS = [
  {
    name: 'doji',
    display: 'Doji',
    bias: 'neutral',
    meaning: 'Open and close ended very close together — neither buyers nor sellers won the period. A pause / indecision candle.',
    when: 'Most meaningful at the END of an existing trend — it can hint that the current direction is losing steam.',
    fail: 'A doji in the middle of a sideways range is just noise. Doji are common; not every one is a turning point.',
    confirm: 'Wait for the NEXT 1–2 candles. If they push the opposite way of the prior trend, the pause turned into a turn. If they continue the trend, the doji was just a breather.',
    svg: dojiSVG(),
  },
  {
    name: 'hammer',
    display: 'Hammer',
    bias: 'bullish',
    meaning: 'A small body near the top, with a long lower wick. Sellers pushed price down hard but buyers reclaimed it by the close.',
    when: 'Strongest after a clear DOWNTREND — it can mark exhaustion of selling.',
    fail: 'In a sideways or rising market a hammer is just a normal candle and means nothing.',
    confirm: 'Look for a follow-through green candle the next day with rising volume. No follow-through = the hammer was bait.',
    svg: hammerSVG(),
  },
  {
    name: 'shooting_star',
    display: 'Shooting Star',
    bias: 'bearish',
    meaning: 'A small body near the bottom, with a long upper wick. Buyers pushed price up hard but sellers slammed it back down.',
    when: 'Strongest after a clear UPTREND — it can mark exhaustion of buying.',
    fail: 'In a sideways or falling market a shooting star is just a normal candle.',
    confirm: 'Look for a follow-through red candle the next day with rising volume.',
    svg: shootingStarSVG(),
  },
  {
    name: 'marubozu',
    display: 'Marubozu (full body)',
    bias: 'neutral',
    meaning: 'A full-body candle with little to no wicks. One side dominated the entire period — strong conviction.',
    when: 'Bullish marubozu after a downtrend = aggressive buying. Bearish marubozu after an uptrend = aggressive selling.',
    fail: 'On its own, a marubozu can also be a "blow-off" — i.e. the last burst before a reversal.',
    confirm: 'Watch the next session: continuation in the same direction confirms conviction; an immediate reversal candle suggests a blow-off.',
    svg: marubozuSVG(),
  },
  {
    name: 'bullish_engulfing',
    display: 'Bullish Engulfing',
    bias: 'bullish',
    meaning: 'A small red candle followed by a big green candle whose body completely "swallows" the previous body — buyers took control.',
    when: 'Strongest after a downtrend, near a known support level.',
    fail: 'In a choppy / sideways tape, engulfings are common and meaningless.',
    confirm: 'Volume on the engulfing candle should be NOTABLY higher than the prior candle. Without volume, the swallow is suspect.',
    svg: bullishEngulfingSVG(),
  },
  {
    name: 'bearish_engulfing',
    display: 'Bearish Engulfing',
    bias: 'bearish',
    meaning: 'A small green candle followed by a big red candle whose body completely "swallows" the previous body — sellers took control.',
    when: 'Strongest after an uptrend, near a known resistance level.',
    fail: 'In a choppy / sideways tape, engulfings are common and meaningless.',
    confirm: 'Volume on the engulfing candle should be NOTABLY higher than the prior. Add a follow-through red candle to be confident.',
    svg: bearishEngulfingSVG(),
  },
  {
    name: 'morning_star',
    display: 'Morning Star',
    bias: 'bullish',
    meaning: 'Three-bar reversal: big red candle, then a small indecision candle, then a big green candle that closes well into the first red body.',
    when: 'After a clear downtrend.',
    fail: 'If the third candle is weak or has a long upper wick, the reversal is shaky.',
    confirm: 'Volume rising into the third candle and price holding the lows of the middle candle for the next 1–2 days.',
    svg: morningStarSVG(),
  },
  {
    name: 'evening_star',
    display: 'Evening Star',
    bias: 'bearish',
    meaning: 'Three-bar topping pattern: big green candle, small indecision candle, then a big red candle that closes well into the first green body.',
    when: 'After a clear uptrend.',
    fail: 'If the third candle is shallow or quickly reversed, the top isn\'t in.',
    confirm: 'Volume rising into the third candle and price holding below the highs of the middle candle for the next 1–2 days.',
    svg: eveningStarSVG(),
  },
  {
    name: 'bullish_harami',
    display: 'Bullish Harami',
    bias: 'bullish',
    meaning: 'A small bullish candle nested inside the body of the previous bigger bearish candle. Selling pressure paused.',
    when: 'After a downtrend — first sign that sellers may be tired.',
    fail: 'If the next candle resumes selling, the harami was just a pause inside a continuing downtrend.',
    confirm: 'Wait for a bullish follow-through close above the prior open with rising volume.',
    svg: bullishHaramiSVG(),
  },
  {
    name: 'bearish_harami',
    display: 'Bearish Harami',
    bias: 'bearish',
    meaning: 'A small bearish candle nested inside the body of the previous bigger bullish candle. Buying pressure paused.',
    when: 'After an uptrend — first sign that buyers may be tired.',
    fail: 'If the next candle resumes the rally, the harami was just a pause.',
    confirm: 'Wait for a bearish follow-through close below the prior open with rising volume.',
    svg: bearishHaramiSVG(),
  },
];

document.addEventListener('DOMContentLoaded', () => {
  const $g = document.getElementById('pattern-grid');
  $g.innerHTML = PATTERNS.map((p, i) => `
    <button class="pattern-card" data-i="${i}">
      <span class="bias bias-${p.bias}">${p.bias}</span>
      ${p.svg}
      <h4>${p.display}</h4>
      <div class="muted" style="font-size: 12px; line-height:1.5;">${p.meaning.split(' — ')[0]}.</div>
    </button>
  `).join('');
  $g.addEventListener('click', (e) => {
    const card = e.target.closest('.pattern-card');
    if (!card) return;
    document.querySelectorAll('.pattern-card').forEach(c => c.classList.toggle('is-active', c === card));
    showPattern(PATTERNS[+card.dataset.i]);
  });
  // Show the first pattern by default
  const first = document.querySelector('.pattern-card');
  if (first) { first.classList.add('is-active'); showPattern(PATTERNS[0]); }

  // Real-chart lesson
  document.getElementById('learn-go').addEventListener('click', loadRealLesson);
  document.getElementById('learn-ticker').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadRealLesson();
  });
});

function showPattern(p) {
  document.getElementById('pd-title').textContent = p.display;
  const biasEl = document.getElementById('pd-bias');
  biasEl.innerHTML = `<span class="bias bias-${p.bias}">${p.bias}</span>`;
  document.getElementById('pd-vis').innerHTML = p.svg;
  document.getElementById('pd-meaning').textContent = p.meaning;
  document.getElementById('pd-when').textContent = p.when;
  document.getElementById('pd-fail').textContent = p.fail;
  document.getElementById('pd-confirm').textContent = p.confirm;
}

async function loadRealLesson() {
  const ticker = document.getElementById('learn-ticker').value.trim().toUpperCase();
  const $r = document.getElementById('learn-result');
  if (!ticker) { $r.innerHTML = '<div class="muted">Enter a ticker first.</div>'; return; }
  $r.innerHTML = '<div class="empty"><div class="spinner"></div><div style="margin-top:10px;">Fetching chart…</div></div>';
  try {
    const lesson = await API.learn({ ticker, timeframe: '6mo' });
    if (!lesson.ohlcv?.length) {
      $r.innerHTML = `<div class="empty">No price data found for ${ticker}.</div>`;
      return;
    }
    const dets = lesson.detections || [];
    let html = `<div class="muted" style="font-size:13px; margin-bottom:10px;">
      ${lesson.company_name || ticker} · ${lesson.timeframe} · ${lesson.n_bars} bars · last close ${lesson.last_close?.toFixed(2) || 'n/a'}
    </div>`;
    if (lesson.chart_summary) html += `<div class="card" style="margin-bottom:14px;">${lesson.chart_summary}</div>`;
    if (dets.length === 0) {
      html += `<div class="muted">No textbook-grade patterns were detected in this window — that's normal. Real charts are noisy.</div>`;
    } else {
      html += `<h4 style="font-size:14px; margin: 14px 0 6px;">Patterns we found on this chart</h4>`;
      html += `<div class="event-list">${dets.map(d => `
        <div class="event-card ${d.bias}">
          <div class="event-meta">
            <span><strong>${d.pattern.replace(/_/g, ' ')}</strong></span>
            <span>${d.date}</span>
            <span>conf ${(d.confidence * 100).toFixed(0)}%</span>
          </div>
          <div class="event-explain">${d.note}</div>
        </div>
      `).join('')}</div>`;
    }
    $r.innerHTML = html;
  } catch (e) {
    $r.innerHTML = `<div class="empty" style="color: var(--bear);">Could not build lesson: ${e.message}</div>`;
  }
}

// =====================================================================
// Tiny inline SVGs — schematic representations of each pattern.
// =====================================================================
function _candle(x, openY, closeY, highY, lowY, color) {
  const top = Math.min(openY, closeY);
  const bot = Math.max(openY, closeY);
  return `<line x1="${x}" y1="${highY}" x2="${x}" y2="${top}" stroke="#475569" stroke-width="1"/>
          <rect x="${x-7}" y="${top}" width="14" height="${bot-top}" fill="${color}" rx="1"/>
          <line x1="${x}" y1="${bot}" x2="${x}" y2="${lowY}" stroke="#475569" stroke-width="1"/>`;
}
const GREEN = '#10B981', RED = '#EF4444', GRAY = '#94A3B8';

function dojiSVG() {
  return `<svg viewBox="0 0 60 90" width="60" height="90">
    <line x1="30" y1="20" x2="30" y2="70" stroke="#475569"/>
    <line x1="20" y1="44" x2="40" y2="44" stroke="#1E293B" stroke-width="2"/>
  </svg>`;
}
function hammerSVG() {
  return `<svg viewBox="0 0 60 100" width="60" height="100">
    ${_candle(30, 28, 35, 25, 90, GREEN)}
  </svg>`;
}
function shootingStarSVG() {
  return `<svg viewBox="0 0 60 100" width="60" height="100">
    ${_candle(30, 70, 65, 10, 75, RED)}
  </svg>`;
}
function marubozuSVG() {
  return `<svg viewBox="0 0 100 90" width="100" height="90">
    ${_candle(30, 20, 75, 20, 75, GREEN)}
    ${_candle(70, 75, 20, 20, 75, RED)}
  </svg>`;
}
function bullishEngulfingSVG() {
  return `<svg viewBox="0 0 100 90" width="100" height="90">
    ${_candle(30, 35, 55, 30, 60, RED)}
    ${_candle(70, 60, 25, 22, 65, GREEN)}
  </svg>`;
}
function bearishEngulfingSVG() {
  return `<svg viewBox="0 0 100 90" width="100" height="90">
    ${_candle(30, 55, 35, 30, 60, GREEN)}
    ${_candle(70, 25, 60, 22, 65, RED)}
  </svg>`;
}
function morningStarSVG() {
  return `<svg viewBox="0 0 140 90" width="140" height="90">
    ${_candle(25,  20, 60, 18, 65, RED)}
    ${_candle(70,  68, 72, 65, 76, GRAY)}
    ${_candle(115, 60, 25, 20, 65, GREEN)}
  </svg>`;
}
function eveningStarSVG() {
  return `<svg viewBox="0 0 140 90" width="140" height="90">
    ${_candle(25,  60, 20, 18, 65, GREEN)}
    ${_candle(70,  18, 22, 12, 25, GRAY)}
    ${_candle(115, 25, 60, 20, 65, RED)}
  </svg>`;
}
function bullishHaramiSVG() {
  return `<svg viewBox="0 0 100 90" width="100" height="90">
    ${_candle(30, 22, 70, 20, 75, RED)}
    ${_candle(70, 50, 38, 35, 55, GREEN)}
  </svg>`;
}
function bearishHaramiSVG() {
  return `<svg viewBox="0 0 100 90" width="100" height="90">
    ${_candle(30, 70, 22, 18, 75, GREEN)}
    ${_candle(70, 38, 50, 35, 55, RED)}
  </svg>`;
}
