// Quest Mode:
// Game 1: Stock Market Quest (5 missions on live ticker data)
// Game 2: Candlestick Pattern Game (chart marker + multiple choice rounds)

let QUEST = null;
let CANDLE = null;

const TREND_LABELS = {
  uptrend: 'Uptrend',
  downtrend: 'Downtrend',
  sideways: 'Sideways',
  unclear: 'Unclear',
};

const ALL_RISK_CHOICES = [
  'Elevated volatility',
  'Bearish momentum',
  'Conflicting signals',
  'Weak evidence coverage',
  'Stale data',
  'Regulatory event',
  'No major automated risk flag',
];

const STANCE_TEXT = {
  watch: 'Watch only for now',
  research_more: 'Needs more evidence before serious study',
  early_positive_setup: 'Worth studying further (early positive setup)',
  wait_for_confirmation: 'Wait for more confirmation',
  avoid_for_now: 'Risk appears elevated right now',
};

const POLARITY_LABELS = {
  bullish: 'Mostly positive',
  bearish: 'Mostly negative',
  neutral: 'Mixed / neutral',
  insufficient: 'Not enough news',
};

const PATTERN_LIBRARY = [
  'doji',
  'hammer',
  'shooting_star',
  'marubozu',
  'bullish_engulfing',
  'bearish_engulfing',
  'morning_star',
  'evening_star',
  'bullish_harami',
  'bearish_harami',
];

document.addEventListener('DOMContentLoaded', () => {
  const $start = document.getElementById('quest-start');
  const $ticker = document.getElementById('quest-ticker');
  const $missionList = document.getElementById('mission-list');
  const $nextRound = document.getElementById('candle-next');

  $start.addEventListener('click', startQuest);
  $ticker.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') startQuest();
  });
  $missionList.addEventListener('click', onMissionClick);
  document.getElementById('candle-options').addEventListener('click', onCandleOptionClick);
  $nextRound.addEventListener('click', nextCandleRound);
});

async function startQuest() {
  const ticker = (document.getElementById('quest-ticker').value || '').trim().toUpperCase();
  if (!ticker) {
    showQuestError('Enter a ticker first (for example RELIANCE or INFY).');
    return;
  }

  showLoader(true);
  showQuestError('');
  setVisible('quest-missions', false);
  setVisible('candlestick-game', false);

  try {
    const [analyze, lesson] = await Promise.all([
      API.analyze({ ticker, timeframe: '6mo', exchange: 'auto', skipLLM: true }),
      API.learn({ ticker, timeframe: '6mo', exchange: 'auto' }),
    ]);

    const missions = buildQuestMissions(analyze);
    QUEST = {
      ticker,
      analyze,
      lesson,
      missions,
      completed: 0,
      xp: 0,
      streak: 0,
      level: 1,
    };

    document.getElementById('quest-subtitle').textContent =
      `${analyze.company_meta?.long_name || ticker} · complete all 5 missions to unlock the candlestick game`;

    renderMissions();
    updateHud();
    setVisible('quest-missions', true);
  } catch (e) {
    showQuestError(`Could not build quest for ${ticker}: ${e.message}`);
  } finally {
    showLoader(false);
  }
}

function buildQuestMissions(data) {
  const missions = [];

  // Mission 1: Trend
  const trendCorrect = TREND_LABELS[data.trend] || 'Unclear';
  missions.push({
    title: 'Mission 1 · Trend Tracker',
    prompt: 'What is the current chart regime?',
    options: withDistractors(trendCorrect, Object.values(TREND_LABELS), 4),
    correct: trendCorrect,
    why: 'Trend context tells you whether the market is broadly rewarding or rejecting the stock right now.',
    answered: false,
    selected: null,
  });

  // Mission 2: Risk
  const risk = data.risk || {};
  const riskMap = {
    elevated_volatility: 'Elevated volatility',
    bearish_momentum: 'Bearish momentum',
    conflicting_signals: 'Conflicting signals',
    weak_coverage: 'Weak evidence coverage',
    stale_data: 'Stale data',
    regulatory_event: 'Regulatory event',
  };
  const raised = Object.keys(riskMap).filter((k) => !!risk[k]).map((k) => riskMap[k]);
  const riskCorrect = raised[0] || 'No major automated risk flag';
  missions.push({
    title: 'Mission 2 · Risk Radar',
    prompt: 'Which risk signal should you pay attention to first?',
    options: withDistractors(riskCorrect, ALL_RISK_CHOICES, 4),
    correct: riskCorrect,
    why: 'Risk signals help beginners avoid overconfidence before they understand the full picture.',
    answered: false,
    selected: null,
  });

  // Mission 3: News polarity
  const devs = data.developments || [];
  let polarity = 'insufficient';
  if (devs.length) {
    const counts = { bullish: 0, bearish: 0, neutral: 0 };
    devs.slice(0, 8).forEach((d) => {
      counts[d.polarity] = (counts[d.polarity] || 0) + 1;
    });
    if (counts.bullish > counts.bearish && counts.bullish > counts.neutral) polarity = 'bullish';
    else if (counts.bearish > counts.bullish && counts.bearish > counts.neutral) polarity = 'bearish';
    else polarity = 'neutral';
  }
  const polarityCorrect = POLARITY_LABELS[polarity];
  missions.push({
    title: 'Mission 3 · News Pulse',
    prompt: 'What is the dominant recent news tone?',
    options: withDistractors(polarityCorrect, Object.values(POLARITY_LABELS), 4),
    correct: polarityCorrect,
    why: 'News tone is not a trading signal, but repeated negative clusters often deserve deeper study.',
    answered: false,
    selected: null,
  });

  // Mission 4: Health score weakest lens
  const cards = data.health_scorecard || [];
  const weight = { 'Needs Attention': 4, Weak: 3, 'Insufficient Data': 3, Moderate: 2, Strong: 1 };
  let weakest = cards[0]?.name || 'Valuation';
  let worstScore = -1;
  cards.forEach((c) => {
    const w = weight[c.label] || 0;
    if (w > worstScore) {
      weakest = c.name;
      worstScore = w;
    }
  });
  const names = cards.map((c) => c.name);
  missions.push({
    title: 'Mission 4 · Fundamental Lens',
    prompt: 'Which dimension needs the closest follow-up research?',
    options: withDistractors(weakest, names.length ? names : ['Growth', 'Profitability', 'Debt Risk', 'Valuation'], 4),
    correct: weakest,
    why: 'Great investors focus on weak links first, not just strengths.',
    answered: false,
    selected: null,
  });

  // Mission 5: Study verdict
  const stanceLabel = data.stance?.label || 'watch';
  const verdictCorrect = STANCE_TEXT[stanceLabel] || STANCE_TEXT.watch;
  missions.push({
    title: 'Mission 5 · Study Verdict',
    prompt: 'Based on this run, what is the best educational verdict?',
    options: withDistractors(verdictCorrect, Object.values(STANCE_TEXT), 4),
    correct: verdictCorrect,
    why: 'The goal is not buy/sell advice. It is deciding whether this stock is worth deeper study now.',
    answered: false,
    selected: null,
  });

  return missions;
}

function renderMissions() {
  if (!QUEST) return;
  const $list = document.getElementById('mission-list');
  $list.innerHTML = QUEST.missions.map((m, idx) => {
    const locked = idx > QUEST.completed;
    const done = idx < QUEST.completed;
    const active = idx === QUEST.completed;

    const status = done ? 'Complete' : active ? 'In Progress' : 'Locked';
    const statusClass = done ? 'is-done' : active ? 'is-active' : 'is-locked';

    const optionsHtml = m.options.map((opt, oIdx) => {
      const selected = m.selected === opt;
      const correct = m.answered && opt === m.correct;
      const wrong = m.answered && selected && opt !== m.correct;
      return `
        <button class="mission-option ${correct ? 'is-correct' : ''} ${wrong ? 'is-wrong' : ''}"
          data-mission="${idx}" data-option="${oIdx}" ${locked || m.answered ? 'disabled' : ''}>
          ${opt}
        </button>
      `;
    }).join('');

    const feedback = m.answered
      ? `<div class="quest-feedback ${m.selected === m.correct ? 'good' : 'bad'}">
          <strong>${m.selected === m.correct ? 'Correct.' : 'Not quite.'}</strong> ${m.why}
        </div>`
      : '';

    return `
      <article class="mission-card ${statusClass}">
        <div class="mission-head">
          <h3>${m.title}</h3>
          <span class="quest-chip">${status}</span>
        </div>
        <p class="mission-prompt">${m.prompt}</p>
        <div class="mission-options">${optionsHtml}</div>
        ${feedback}
      </article>
    `;
  }).join('');
}

function onMissionClick(e) {
  const btn = e.target.closest('.mission-option');
  if (!btn || !QUEST) return;
  const missionIdx = Number(btn.dataset.mission);
  const optionIdx = Number(btn.dataset.option);

  if (missionIdx !== QUEST.completed) return;
  const mission = QUEST.missions[missionIdx];
  if (!mission || mission.answered) return;

  const pick = mission.options[optionIdx];
  mission.selected = pick;
  mission.answered = true;

  if (pick === mission.correct) {
    QUEST.completed += 1;
    QUEST.streak += 1;
    QUEST.xp += 20 + Math.min(QUEST.streak * 2, 20);
    QUEST.level = Math.floor(QUEST.xp / 80) + 1;
    burstConfetti();
  } else {
    QUEST.completed += 1;
    QUEST.streak = 0;
    QUEST.xp = Math.max(0, QUEST.xp - 4);
    QUEST.level = Math.floor(QUEST.xp / 80) + 1;
  }

  renderMissions();
  updateHud();

  if (QUEST.completed >= QUEST.missions.length) {
    buildCandlestickGame();
  }
}

function updateHud() {
  if (!QUEST) return;
  document.getElementById('quest-xp').textContent = String(QUEST.xp);
  document.getElementById('quest-level').textContent = String(QUEST.level);
  document.getElementById('quest-streak').textContent = String(QUEST.streak);

  const done = QUEST.completed;
  const total = QUEST.missions.length;
  document.getElementById('quest-progress-label').textContent = `${done} / ${total}`;
  document.getElementById('quest-progress-fill').style.width = `${(done / total) * 100}%`;
}

function buildCandlestickGame() {
  if (!QUEST) return;
  setVisible('candlestick-game', true);

  const lesson = QUEST.lesson || {};
  const detections = (lesson.detections || []).slice(0, 5);
  const rounds = detections.length ? detections.map((d) => {
    const correct = normalizePatternName(d.pattern);
    return {
      correct,
      rawPattern: d.pattern,
      date: d.date,
      index: d.index,
      note: d.note,
      options: buildPatternOptions(correct),
    };
  }) : [{
    correct: 'Doji',
    rawPattern: 'doji',
    date: '',
    index: null,
    note: 'No textbook detection surfaced, so this practice round uses a neutral pattern question.',
    options: buildPatternOptions('Doji'),
  }];

  CANDLE = {
    rounds,
    current: 0,
    score: 0,
  };

  renderCandleChart(lesson.ohlcv || [], detections);
  renderCandleRound();
}

function renderCandleChart(ohlcv, detections) {
  const $chart = document.getElementById('candle-chart');
  $chart.innerHTML = '';
  if (!window.LightweightCharts || !ohlcv || !ohlcv.length) {
    $chart.innerHTML = '<div class="empty">Chart data unavailable.</div>';
    return;
  }

  const chart = LightweightCharts.createChart($chart, {
    autoSize: true,
    layout: {
      background: { color: '#0B1020' },
      textColor: '#D7E3FF',
      fontFamily: '"Space Grotesk", "Inter", sans-serif',
    },
    rightPriceScale: { borderColor: '#2D3D66' },
    timeScale: { borderColor: '#2D3D66' },
    grid: {
      vertLines: { color: 'rgba(148, 163, 184, 0.12)' },
      horzLines: { color: 'rgba(148, 163, 184, 0.12)' },
    },
  });
  const series = chart.addCandlestickSeries({
    upColor: '#21D19F',
    downColor: '#F75B7A',
    borderVisible: false,
    wickUpColor: '#21D19F',
    wickDownColor: '#F75B7A',
  });

  const rows = ohlcv.map((b) => ({
    time: (b.Date || '').slice(0, 10),
    open: Number(b.Open),
    high: Number(b.High),
    low: Number(b.Low),
    close: Number(b.Close),
  })).filter((b) => b.time && Number.isFinite(b.open) && Number.isFinite(b.close));

  series.setData(rows);

  if (detections && detections.length) {
    const markers = detections.slice(0, 8).map((d, i) => {
      const row = ohlcv[d.index] || {};
      const time = String(row.Date || '').slice(0, 10);
      return {
        time,
        position: d.bias === 'bearish' ? 'aboveBar' : 'belowBar',
        color: d.bias === 'bearish' ? '#F75B7A' : d.bias === 'bullish' ? '#21D19F' : '#65B5FF',
        shape: 'circle',
        text: String(i + 1),
      };
    }).filter((m) => !!m.time);
    if (series.setMarkers) series.setMarkers(markers);
  }

  chart.timeScale().fitContent();
}

function renderCandleRound() {
  if (!CANDLE) return;
  const round = CANDLE.rounds[CANDLE.current];
  const total = CANDLE.rounds.length;

  document.getElementById('candle-round-title').textContent = `Round ${CANDLE.current + 1}`;
  document.getElementById('candle-round-chip').textContent = `${CANDLE.current + 1} / ${total}`;
  document.getElementById('candle-question').textContent =
    `Identify the pattern${round.date ? ` (${round.date})` : ''}`;

  document.getElementById('candle-options').innerHTML = round.options.map((opt, idx) => `
    <button class="mission-option" data-candle-opt="${idx}">${opt}</button>
  `).join('');

  document.getElementById('candle-feedback').textContent = '';
  setVisible('candle-next', false);
}

function onCandleOptionClick(e) {
  const btn = e.target.closest('[data-candle-opt]');
  if (!btn || !CANDLE) return;

  const idx = Number(btn.dataset.candleOpt);
  const round = CANDLE.rounds[CANDLE.current];
  const pick = round.options[idx];

  const all = Array.from(document.querySelectorAll('[data-candle-opt]'));
  all.forEach((b) => { b.disabled = true; });

  const $feedback = document.getElementById('candle-feedback');
  if (pick === round.correct) {
    btn.classList.add('is-correct');
    $feedback.className = 'quest-feedback good';
    $feedback.innerHTML = `<strong>Correct.</strong> ${round.note}`;
    CANDLE.score += 1;
    if (QUEST) {
      QUEST.xp += 16;
      QUEST.streak += 1;
      QUEST.level = Math.floor(QUEST.xp / 80) + 1;
      updateHud();
    }
    burstConfetti();
  } else {
    btn.classList.add('is-wrong');
    const correctBtn = all.find((b) => b.textContent === round.correct);
    if (correctBtn) correctBtn.classList.add('is-correct');
    $feedback.className = 'quest-feedback bad';
    $feedback.innerHTML = `<strong>Not this one.</strong> Correct answer: <strong>${round.correct}</strong>. ${round.note}`;
    if (QUEST) {
      QUEST.streak = 0;
      updateHud();
    }
  }
  setVisible('candle-next', true);
}

function nextCandleRound() {
  if (!CANDLE) return;
  CANDLE.current += 1;
  if (CANDLE.current >= CANDLE.rounds.length) {
    const $opts = document.getElementById('candle-options');
    $opts.innerHTML = '';
    const $fb = document.getElementById('candle-feedback');
    $fb.className = 'quest-feedback good';
    $fb.innerHTML = `<strong>Game complete.</strong> You scored ${CANDLE.score}/${CANDLE.rounds.length}.`;
    setVisible('candle-next', false);
    return;
  }
  renderCandleRound();
}

function normalizePatternName(name) {
  const n = String(name || '').toLowerCase();
  if (n === 'shooting_star') return 'Shooting Star';
  if (n === 'bullish_engulfing') return 'Bullish Engulfing';
  if (n === 'bearish_engulfing') return 'Bearish Engulfing';
  if (n === 'morning_star') return 'Morning Star';
  if (n === 'evening_star') return 'Evening Star';
  if (n === 'bullish_harami') return 'Bullish Harami';
  if (n === 'bearish_harami') return 'Bearish Harami';
  if (n.startsWith('marubozu')) return 'Marubozu';
  return n.split('_').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
}

function buildPatternOptions(correct) {
  const labels = PATTERN_LIBRARY.map(normalizePatternName);
  return withDistractors(correct, labels, 4);
}

function withDistractors(correct, pool, size) {
  const unique = Array.from(new Set((pool || []).filter(Boolean)));
  const without = unique.filter((x) => x !== correct);
  shuffle(without);
  return shuffle([correct, ...without.slice(0, Math.max(0, size - 1))]);
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    const tmp = a[i];
    a[i] = a[j];
    a[j] = tmp;
  }
  return a;
}

function showLoader(isLoading) {
  setVisible('quest-loader', isLoading);
}

function showQuestError(msg) {
  const $err = document.getElementById('quest-error');
  if (!msg) {
    $err.classList.add('hidden');
    $err.textContent = '';
    return;
  }
  $err.classList.remove('hidden');
  $err.textContent = msg;
}

function setVisible(id, visible) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('hidden', !visible);
}

function burstConfetti() {
  for (let i = 0; i < 18; i += 1) {
    const bit = document.createElement('span');
    bit.className = 'confetti-bit';
    bit.style.left = `${Math.random() * 100}%`;
    bit.style.background = ['#6D5BFF', '#1FD6A5', '#FFB020', '#FF5D7A', '#6FB6FF'][i % 5];
    bit.style.animationDelay = `${Math.random() * 0.15}s`;
    document.body.appendChild(bit);
    setTimeout(() => bit.remove(), 1200);
  }
}
