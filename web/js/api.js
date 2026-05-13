// Tiny fetch wrapper — uses same-origin so it works whether served from
// uvicorn or any static server.

const API = {
  async search(q) {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q || '')}`);
    if (!r.ok) throw new Error(`search failed: ${r.status}`);
    return (await r.json()).results;
  },
  async analyze({ ticker, timeframe = '6mo', exchange = 'auto', skipLLM = true }) {
    const url = `/api/analyze?ticker=${encodeURIComponent(ticker)}` +
                `&timeframe=${encodeURIComponent(timeframe)}` +
                `&exchange=${encodeURIComponent(exchange)}` +
                `&skip_llm=${skipLLM ? 'true' : 'false'}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json()).detail || `analyze failed: ${r.status}`);
    return await r.json();
  },
  async learn({ ticker = '', timeframe = '6mo', exchange = 'auto' }) {
    const url = `/api/learn?ticker=${encodeURIComponent(ticker)}` +
                `&timeframe=${encodeURIComponent(timeframe)}` +
                `&exchange=${encodeURIComponent(exchange)}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`learn failed: ${r.status}`);
    return await r.json();
  },
  async glossary() {
    const r = await fetch('/api/glossary');
    if (!r.ok) throw new Error(`glossary failed: ${r.status}`);
    return (await r.json()).glossary;
  },
};

// Shared search-box widget — reused by index.html and dashboard.html.
function bindSearchBox({ inputId, suggestionsId, goId, onSubmit }) {
  const $input = document.getElementById(inputId);
  const $sugg  = document.getElementById(suggestionsId);
  const $go    = document.getElementById(goId);
  if (!$input || !$sugg || !$go) return;

  let timer = null;
  let activeIdx = -1;
  let currentResults = [];

  const closeSuggestions = () => { $sugg.classList.remove('is-open'); activeIdx = -1; };
  const openSuggestions  = () => { if (currentResults.length) $sugg.classList.add('is-open'); };

  const renderSuggestions = (items) => {
    currentResults = items || [];
    if (!items || items.length === 0) {
      $sugg.innerHTML = '';
      closeSuggestions();
      return;
    }
    $sugg.innerHTML = items.map((it, i) =>
      `<div class="suggestion" data-i="${i}">
         <div>
           <div class="suggestion-symbol">${it.symbol}</div>
           <div class="suggestion-name">${it.name}</div>
         </div>
         <span class="suggestion-exch">${it.exchange}</span>
       </div>`
    ).join('');
    openSuggestions();
    $sugg.querySelectorAll('.suggestion').forEach(el => {
      el.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const idx = +el.dataset.i;
        $input.value = currentResults[idx].symbol;
        closeSuggestions();
        onSubmit(currentResults[idx].symbol);
      });
    });
  };

  const fetchSuggestions = async (q) => {
    try {
      const items = await API.search(q);
      renderSuggestions(items);
    } catch (e) { console.error(e); }
  };

  $input.addEventListener('focus', () => fetchSuggestions($input.value));
  $input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => fetchSuggestions($input.value), 120);
  });
  $input.addEventListener('blur', () => setTimeout(closeSuggestions, 150));
  $input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const v = $input.value.trim();
      if (v) onSubmit(v.toUpperCase());
    } else if (e.key === 'Escape') {
      closeSuggestions();
    }
  });
  $go.addEventListener('click', () => {
    const v = $input.value.trim();
    if (v) onSubmit(v.toUpperCase());
  });
}
