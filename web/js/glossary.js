// Glossary page — fetches /api/glossary then filters client-side.

let ALL = [];
let activeCat = '';

document.addEventListener('DOMContentLoaded', async () => {
  try {
    ALL = await API.glossary();
    render();
  } catch (e) {
    document.getElementById('glossary-grid').innerHTML =
      `<div class="empty" style="color: var(--bear);">Could not load glossary: ${e.message}</div>`;
  }
  document.getElementById('glossary-search').addEventListener('input', render);
  document.querySelectorAll('[data-cat]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-cat]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeCat = btn.dataset.cat;
      render();
    });
  });
});

function render() {
  const q = document.getElementById('glossary-search').value.trim().toLowerCase();
  const filtered = ALL.filter(it => {
    if (activeCat && it.category !== activeCat) return false;
    if (!q) return true;
    if (it.term.toLowerCase().includes(q)) return true;
    if ((it.aliases || []).some(a => a.toLowerCase().includes(q))) return true;
    if (it.meaning.toLowerCase().includes(q)) return true;
    return false;
  });
  const $g = document.getElementById('glossary-grid');
  const $empty = document.getElementById('glossary-empty');
  if (filtered.length === 0) {
    $g.innerHTML = '';
    $empty.classList.remove('hidden');
    return;
  }
  $empty.classList.add('hidden');
  $g.innerHTML = filtered.map(it => `
    <div class="glossary-item">
      <div class="cat">${it.category}</div>
      <h4>${it.term}</h4>
      <div class="def">${it.meaning}</div>
      <div class="why"><strong>Why it matters:</strong> ${it.why_it_matters}</div>
    </div>
  `).join('');
}
