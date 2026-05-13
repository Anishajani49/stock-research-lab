// Dashboard — fetches the analysis JSON and renders all sections.

document.addEventListener('DOMContentLoaded', () => {
  bindSearchBox({
    inputId: 'search-input',
    suggestionsId: 'search-suggestions',
    goId: 'search-go',
    onSubmit: (symbol) => loadDashboard(symbol),
  });

  // Tabs
  document.getElementById('tabs').addEventListener('click', (e) => {
    const btn = e.target.closest('.tab');
    if (!btn) return;
    document.querySelectorAll('#tabs .tab').forEach(t => t.classList.toggle('active', t === btn));
    const target = btn.dataset.tab;
    document.querySelectorAll('[data-pane]').forEach(p =>
      p.classList.toggle('hidden', p.dataset.pane !== target)
    );
  });

  // Auto-load if ?ticker=... in URL
  const params = new URLSearchParams(window.location.search);
  const t = params.get('ticker');
  if (t) {
    document.getElementById('search-input').value = t;
    loadDashboard(t);
  }
});

async function loadDashboard(ticker) {
  const $loader = document.getElementById('loader');
  const $err    = document.getElementById('error');
  const $ph     = document.getElementById('placeholder');
  const $dash   = document.getElementById('dash');

  $ph.classList.add('hidden');
  $err.classList.add('hidden');
  $dash.classList.add('hidden');
  $loader.classList.remove('hidden');

  // Update URL so refresh works
  const newUrl = `/dashboard?ticker=${encodeURIComponent(ticker)}`;
  window.history.replaceState({}, '', newUrl);

  try {
    const data = await API.analyze({ ticker, timeframe: '6mo', skipLLM: true });
    renderDashboard(data);
    $loader.classList.add('hidden');
    $dash.classList.remove('hidden');
  } catch (e) {
    $loader.classList.add('hidden');
    $err.classList.remove('hidden');
    $err.textContent = `Could not analyze ${ticker}: ${e.message}`;
  }
}

// =====================================================================
// Renderers
// =====================================================================

function fmtNum(v, digits = 2) {
  if (v === null || v === undefined) return 'n/a';
  const f = Number(v);
  if (!isFinite(f)) return 'n/a';
  return f.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
function fmtMoney(v, currency = 'INR', digits = 2) {
  const sym = currency === 'INR' ? '₹' : '';
  if (v === null || v === undefined) return 'n/a';
  return sym + fmtNum(v, digits);
}
function fmtPct(v, digits = 2) {
  if (v === null || v === undefined) return 'n/a';
  let f = Number(v);
  if (Math.abs(f) <= 1.5) f = f * 100;
  return f.toFixed(digits) + '%';
}
function fmtMarketCapINR(v) {
  if (v === null || v === undefined) return 'n/a';
  const cr = Number(v) / 1e7;
  if (cr >= 1e5) return `₹${(cr / 1e5).toFixed(2)} lakh Cr`;
  return `₹${cr.toFixed(0)} Cr`;
}
function badgeClassForLabel(label) {
  switch (label) {
    case 'Strong': return 'badge-strong';
    case 'Moderate': return 'badge-moderate';
    case 'Weak': return 'badge-weak';
    case 'Needs Attention': return 'badge-needs';
    default: return 'badge-na';
  }
}
function stanceClass(label) {
  return ({
    watch: 'stance-watch',
    research_more: 'stance-research',
    early_positive_setup: 'stance-positive',
    wait_for_confirmation: 'stance-wait',
    avoid_for_now: 'stance-avoid',
  }[label] || 'stance-watch');
}
function stanceLabel(label) {
  return ({
    watch: '👀 Watch',
    research_more: '🔍 Research more',
    early_positive_setup: '🟢 Early positive setup',
    wait_for_confirmation: '🟡 Wait for confirmation',
    avoid_for_now: '🔴 Avoid for now',
  }[label] || label);
}

function renderDashboard(data) {
  const meta = data.company_meta || {};
  const snap = data.indicators || {};
  const summary = data.price_series_summary || {};
  const ccy = meta.currency || 'INR';

  // ----- Header -----
  document.getElementById('company-name').textContent = meta.long_name || data.ticker;
  const metaRow = document.getElementById('meta-row');
  metaRow.innerHTML = `
    <span class="meta-tag">Ticker: <strong>${data.ticker}</strong></span>
    ${meta.sector ? `<span class="meta-tag">Sector: ${meta.sector}</span>` : ''}
    ${meta.industry ? `<span class="meta-tag">Industry: ${meta.industry}</span>` : ''}
    ${meta.exchange ? `<span class="meta-tag">${meta.exchange}</span>` : ''}
    <span class="stance-pill ${stanceClass(data.stance.label)}">${stanceLabel(data.stance.label)}</span>
  `;

  // ----- Headline stats -----
  const pct = summary.period_return_pct;
  const arrow = pct > 0 ? '▲' : pct < 0 ? '▼' : '◆';
  document.getElementById('stats').innerHTML = `
    <div class="stat">
      <div class="stat-label">Last Close</div>
      <div class="stat-value">${fmtMoney(snap.last_close, ccy)}</div>
      <div class="stat-sub ${pct > 0 ? 'stat-up' : pct < 0 ? 'stat-down' : ''}">${arrow} ${fmtNum(pct, 1)}% over ${data.timeframe}</div>
    </div>
    <div class="stat">
      <div class="stat-label">52-Week High</div>
      <div class="stat-value">${fmtMoney(data.fundamentals?.fifty_two_week_high, ccy)}</div>
    </div>
    <div class="stat">
      <div class="stat-label">52-Week Low</div>
      <div class="stat-value">${fmtMoney(data.fundamentals?.fifty_two_week_low, ccy)}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Market Cap</div>
      <div class="stat-value">${fmtMarketCapINR(meta.market_cap)}</div>
    </div>
    <div class="stat">
      <div class="stat-label">P/E (Trailing)</div>
      <div class="stat-value">${fmtNum(meta.pe || data.fundamentals?.trailing_pe, 1)}</div>
      <div class="stat-sub">price ÷ profit per share</div>
    </div>
    <div class="stat">
      <div class="stat-label">Trend</div>
      <div class="stat-value" style="text-transform: capitalize;">${data.trend}</div>
      <div class="stat-sub">${data.confidence} confidence</div>
    </div>
  `;

  // ----- Stance callout + Why-this-view tab -----
  renderStanceExplanation(data);

  // ----- A. Business description -----
  const bizDesc = `${meta.long_name || data.ticker} operates in the ${meta.industry || 'unspecified'} industry, classified under the ${meta.sector || 'unspecified'} sector. Listed on ${meta.exchange || 'an Indian exchange'}.`;
  document.getElementById('biz-desc').textContent = bizDesc;

  // ----- B. Fundamentals table -----
  renderFundamentals(data);

  // ----- C. Health scorecard -----
  renderHealthScorecard(data);

  // ----- D. Chart + indicators -----
  renderChart(data);
  renderIndicators(data);

  // ----- E. News + upcoming events -----
  renderUpcomingEvents(data);
  renderNews(data);

  // ----- F. Workflow -----
  renderWorkflow(data);

  // ----- G. Beginner summary -----
  renderSummary(data);
}

function renderFundamentals(data) {
  const f = data.fundamentals || {};
  const $tb = document.getElementById('fund-body');
  const rows = [
    ['Trailing P/E', fmtNum(f.trailing_pe, 1), 'What investors pay today per ₹1 of last year\'s profit. Higher = more optimism (or expensive).'],
    ['Forward P/E', fmtNum(f.forward_pe, 1), 'Same idea but using next year\'s expected profit.'],
    ['Price-to-Book', fmtNum(f.price_to_book, 1), 'Price vs the company\'s net assets. >3 = priced rich vs accounting book value.'],
    ['Book value / share', fmtMoney(f.book_value, 'INR', 1), 'Net assets per share — a sanity floor for valuation.'],
    ['Dividend yield', fmtPct(f.dividend_yield), 'Annual cash you\'d get as a % of today\'s share price.'],
    ['Payout ratio', fmtPct(f.payout_ratio), '% of profit paid out as dividends. Very high = limited reinvestment room.'],
    ['Return on Equity (ROE)', fmtPct(f.return_on_equity), 'Profit on shareholders\' money. >15% is generally healthy.'],
    ['Debt-to-Equity', fmtNum(f.debt_to_equity, 0), 'Debt vs shareholder equity. Lower = safer; >100 may need a closer look.'],
    ['Current ratio', fmtNum(f.current_ratio, 2), 'Short-term assets vs short-term liabilities. >1 means the company can pay near-term bills.'],
    ['Profit margin', fmtPct(f.profit_margin), 'Profit as a % of revenue. Higher = more pricing power / operating efficiency.'],
    ['Revenue growth', fmtPct(f.revenue_growth), 'Year-over-year revenue change.'],
    ['Earnings growth', fmtPct(f.earnings_growth), 'Year-over-year profit change.'],
    ['Beta', fmtNum(f.beta, 2), 'Volatility vs the market. 1 = moves with market; >1 = swings more.'],
  ].filter(r => r[1] !== 'n/a');

  if (rows.length === 0) {
    $tb.innerHTML = `<tr><td colspan="3" class="muted">Fundamentals were not available from the data feed for this ticker.</td></tr>`;
    return;
  }
  $tb.innerHTML = rows.map(([m, v, why]) => `
    <tr><td class="metric">${m}</td><td class="value">${v}</td><td class="meaning">${why}</td></tr>
  `).join('');
}

function renderHealthScorecard(data) {
  const cards = data.health_scorecard || [];
  const $g = document.getElementById('health-grid');
  $g.innerHTML = cards.map(c => `
    <div class="health-cell">
      <div class="top">
        <div class="name">${c.name}</div>
        <span class="badge ${badgeClassForLabel(c.label)}">${c.label}</span>
      </div>
      <div class="finding">${c.finding}</div>
      <div class="why"><strong>Why pros care:</strong> ${c.why_pros_care}</div>
    </div>
  `).join('');
}

function renderChart(data) {
  const $c = document.getElementById('chart-container');
  $c.innerHTML = '';
  const ohlcv = data.ohlcv || [];
  if (!window.LightweightCharts || !ohlcv.length) {
    $c.innerHTML = '<div class="empty">Chart data unavailable.</div>';
    document.getElementById('trend-narrative').textContent = '';
    return;
  }
  const chart = LightweightCharts.createChart($c, {
    autoSize: true,
    layout: { background: { color: '#FFFFFF' }, textColor: '#475569', fontFamily: '-apple-system, system-ui, Inter' },
    rightPriceScale: { borderColor: '#E2E8F0' },
    timeScale: { borderColor: '#E2E8F0', timeVisible: false },
    grid: { vertLines: { color: '#F1F5F9' }, horzLines: { color: '#F1F5F9' } },
  });
  const series = chart.addCandlestickSeries({
    upColor: '#10B981', downColor: '#EF4444',
    wickUpColor: '#10B981', wickDownColor: '#EF4444',
    borderVisible: false,
  });
  series.setData(ohlcv.map(b => ({
    time: (b.Date || '').slice(0, 10),
    open: Number(b.Open), high: Number(b.High),
    low: Number(b.Low), close: Number(b.Close),
  })));

  // Trend narrative
  const snap = data.indicators || {};
  const summ = data.price_series_summary || {};
  const above = (snap.last_close && snap.sma50) ? (snap.last_close > snap.sma50 ? 'above' : 'below') : 'n/a';
  const trendBits = [];
  trendBits.push(`Trend label: <strong>${data.trend}</strong>.`);
  if (summ.period_return_pct !== undefined) trendBits.push(`Period return: <strong>${fmtNum(summ.period_return_pct, 1)}%</strong>.`);
  if (above !== 'n/a') trendBits.push(`Price is <strong>${above}</strong> the 50-day average.`);
  if (snap.rsi14 != null) trendBits.push(`RSI is <strong>${snap.rsi14.toFixed(0)}</strong>.`);
  document.getElementById('trend-narrative').innerHTML = trendBits.join(' ');
}

function renderIndicators(data) {
  const snap = data.indicators || {};
  const rows = [
    ['Price vs SMA50',
      (snap.last_close && snap.sma50) ? (snap.last_close > snap.sma50 ? 'Above' : 'Below') : 'n/a',
      'Price above its 50-day average means recent momentum is positive.'],
    ['RSI 14',
      snap.rsi14 != null ? snap.rsi14.toFixed(1) : 'n/a',
      'Below 30 = heavily sold (possible bounce). Above 70 = heavily bought (possible cool-off).'],
    ['MACD histogram',
      snap.macd_hist != null ? snap.macd_hist.toFixed(3) : 'n/a',
      'Positive = buyers stronger; negative = sellers stronger.'],
    ['ATR 14 (volatility)',
      snap.atr14 != null ? snap.atr14.toFixed(2) : 'n/a',
      'Average daily price swing. Higher = more volatile.'],
    ['Volume trend',
      snap.volume_trend || 'n/a',
      'Rising volume = growing interest; falling = fading interest.'],
  ];
  document.getElementById('indicators-rows').innerHTML = rows.map(([m, v, why]) => `
    <div class="health-cell">
      <div class="top"><div class="name">${m}</div><span class="badge badge-na mono">${v}</span></div>
      <div class="finding">${why}</div>
    </div>
  `).join('');
}

function renderUpcomingEvents(data) {
  const events = data.upcoming_events || [];
  const $list = document.getElementById('upcoming-events');
  if (!events.length) {
    $list.innerHTML = `<div class="muted">No upcoming events surfaced. Indian companies usually announce results dates 1–2 weeks in advance — check again closer to the next quarter.</div>`;
    return;
  }
  const icons = { earnings: '📊', ex_dividend: '💰', dividend_payment: '💵', last_split: '✂️' };
  $list.innerHTML = events.slice(0, 8).map(ev => {
    const days = ev.days_until;
    let when = ev.date || '';
    if (days != null) {
      if (days < 0) when = `${ev.date} (${Math.abs(days)}d ago)`;
      else if (days === 0) when = `${ev.date} (today)`;
      else if (days === 1) when = `${ev.date} (tomorrow)`;
      else when = `${ev.date} (in ${days} days)`;
    }
    return `
      <div class="event-card neutral">
        <div class="event-meta"><span>${icons[ev.kind] || '📅'} ${ev.title || ev.kind}</span><span>${when}</span></div>
        ${ev.note ? `<div class="event-explain">${ev.note}</div>` : ''}
      </div>`;
  }).join('');
}

function renderNews(data) {
  const items = (data.developments || []).slice(0, 8);
  const $list = document.getElementById('news-list');
  if (!items.length) {
    $list.innerHTML = `<div class="muted">No company-specific news surfaced in this run — only general market coverage. Try again later, or check a longer timeframe.</div>`;
    return;
  }
  const friendlyCat = {
    regulatory: ['⚖️ Regulator action', 'the market regulator (SEBI / RBI / govt) took an action'],
    legal:      ['🚓 Legal / fraud',     'a court case, fraud probe, or arrest was reported'],
    earnings:   ['📊 Earnings update',   'the company reported quarterly numbers or a results-related update'],
    rating:     ['📈 Analyst rating',    'a brokerage upgraded or downgraded the stock'],
    leadership: ['👤 Leadership change', 'a top executive joined, left, or was reshuffled'],
    corporate:  ['🏢 Corporate action',  'a merger, demerger, buyback, dividend, or split'],
    product:    ['🧪 Business news',     'a new product, contract, plant, or partnership'],
    macro:      ['🌍 Market-wide news',  'broader market / sector news, not specific to the company'],
    other:      ['📰 General news',      'general coverage that mentions the company'],
  };
  $list.innerHTML = items.map(ev => {
    const [catLabel, catMeaning] = friendlyCat[ev.category] || friendlyCat.other;
    const polClass = ev.polarity || 'neutral';
    const age = ev.age_days != null
      ? (ev.age_days < 1 ? 'today' : `${Math.round(ev.age_days)} day${Math.round(ev.age_days) !== 1 ? 's' : ''} ago`)
      : '';
    return `
      <div class="event-card ${polClass}">
        <div class="event-meta">
          <span>${catLabel}</span>
          <span>${ev.source || 'unknown source'}</span>
          <span>${age}</span>
        </div>
        <h5>${ev.title}</h5>
        <div class="event-explain"><strong>Why we noticed:</strong> ${catMeaning}.</div>
      </div>`;
  }).join('');
}

function renderWorkflow(data) {
  const steps = data.analyst_workflow || [];
  const $w = document.getElementById('workflow');
  if (!steps.length) { $w.innerHTML = '<div class="muted">Workflow not available.</div>'; return; }
  $w.innerHTML = steps.map(s => {
    if (s.step === 8) return ''; // summary rendered separately
    return `
      <div class="step">
        <div class="step-head">
          <div class="step-num">${s.step}</div>
          <h4>${s.title}</h4>
        </div>
        <ul class="qs">${(s.questions || []).map(q => `<li>${q}</li>`).join('')}</ul>
        <div class="obs"><strong>What this stock shows:</strong> ${s.observation}</div>
        ${s.beginner_tip ? `<div class="tip">${s.beginner_tip}</div>` : ''}
      </div>`;
  }).join('');
}

function renderStanceExplanation(data) {
  const exp = data.stance_explanation || {};
  // Top callout
  document.getElementById('stance-pretty').textContent = exp.label_pretty || '—';
  document.getElementById('stance-headline').textContent = exp.headline || '';
  document.getElementById('stance-meaning').textContent = exp.beginner_meaning || '';
  document.getElementById('stance-confidence').textContent =
    `${exp.confidence || '—'} (${(exp.confidence_score ?? 0).toFixed(2)})`;

  // Toggle "Show the logic" → jump to the Why tab
  const $toggle = document.getElementById('stance-toggle');
  $toggle.onclick = () => {
    document.querySelectorAll('#tabs .tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === 'why')
    );
    document.querySelectorAll('[data-pane]').forEach(p =>
      p.classList.toggle('hidden', p.dataset.pane !== 'why')
    );
    document.querySelector('[data-pane="why"]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // ----- Rules the engine fired -----
  const $rules = document.getElementById('why-rules');
  const rules = exp.rules_fired || [];
  if (!rules.length) {
    $rules.innerHTML = '<div class="muted">No specific rules fired — this was the default fall-through verdict.</div>';
  } else {
    $rules.innerHTML = rules.map((r, i) => `
      <div class="event-card neutral">
        <div class="event-meta"><span><strong>Rule ${i + 1}</strong></span></div>
        <h5 style="margin: 4px 0 6px;">${r.reason}</h5>
        ${r.plain_english
          ? `<div class="event-explain"><strong>Plain English:</strong> ${r.plain_english}.</div>`
          : ''}
      </div>
    `).join('');
  }

  // ----- What would change this view -----
  const $changes = document.getElementById('why-changes');
  const changes = exp.what_changes_view || [];
  if (!changes.length) {
    $changes.innerHTML = '<li class="muted">No update criteria produced.</li>';
  } else {
    $changes.innerHTML = changes.map(c => `
      <li style="padding: 8px 12px; background: var(--surface-2); border: 1px solid var(--line);
                 border-radius: var(--r-sm); font-size: 13px; color: var(--ink);">
        ${c}
      </li>
    `).join('');
  }

  // ----- Bull / bear points the engine collected -----
  const $bull = document.getElementById('why-bull');
  const $bear = document.getElementById('why-bear');
  const bull = exp.bull_points || [];
  const bear = exp.bear_points || [];
  $bull.innerHTML = bull.length
    ? bull.map(p => `<li>${p}</li>`).join('')
    : '<li class="muted">No clearly bullish items collected.</li>';
  $bear.innerHTML = bear.length
    ? bear.map(p => `<li>${p}</li>`).join('')
    : '<li class="muted">No clearly bearish items collected.</li>';

  // ----- Five-verdict reference -----
  const $defs = document.getElementById('why-definitions');
  const defs = exp.stance_definitions || {};
  const order = ['watch', 'research_more', 'early_positive_setup', 'wait_for_confirmation', 'avoid_for_now'];
  $defs.innerHTML = order.filter(k => defs[k]).map(k => {
    const isCurrent = k === exp.label;
    return `
      <div class="health-cell" style="${isCurrent ? 'border-color: var(--accent); box-shadow: 0 0 0 2px rgba(79,70,229,.12);' : ''}">
        <div class="top">
          <div class="name">${defs[k].pretty}</div>
          ${isCurrent ? '<span class="badge badge-strong">Current</span>' : ''}
        </div>
        <div class="finding"><strong>${defs[k].tagline}</strong></div>
        <div class="why"><strong>When it fires:</strong> ${defs[k].trigger}</div>
      </div>`;
  }).join('');
}

function renderSummary(data) {
  const summary = (data.analyst_workflow || []).find(s => s.step === 8);
  const $b = document.getElementById('summary-body');
  if (!summary) { $b.innerHTML = '<div class="muted">Summary not available.</div>'; return; }
  $b.innerHTML = `
    <div class="summary-grid">
      <div class="summary-cell good">
        <h5>✅ What looks good</h5>
        <ul>${summary.looks_good.map(x => `<li>${x}</li>`).join('')}</ul>
      </div>
      <div class="summary-cell risky">
        <h5>⚠️ What looks risky</h5>
        <ul>${summary.looks_risky.map(x => `<li>${x}</li>`).join('')}</ul>
      </div>
      <div class="summary-cell research">
        <h5>📚 What needs more research</h5>
        <ul>${summary.needs_research.map(x => `<li>${x}</li>`).join('')}</ul>
      </div>
    </div>
    <div class="card" style="background: var(--surface-2); margin-top: 8px;">
      <h4 style="margin: 0 0 8px;">🎓 Beginner lesson</h4>
      <p class="muted" style="margin:0; font-size: 14px; line-height: 1.65;">${summary.beginner_lesson}</p>
    </div>
    <div class="muted" style="font-size: 12px; margin-top: 14px;">${summary.compliance_note}</div>
  `;
}
