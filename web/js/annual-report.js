// Annual Report Lab — POST a URL or upload a PDF, then render the guided tour.

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('ar-go').addEventListener('click', submit);
  document.getElementById('ar-url').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submit();
  });
});

async function submit() {
  const url = document.getElementById('ar-url').value.trim();
  const file = document.getElementById('ar-file').files[0];
  const hint = document.getElementById('ar-hint').value.trim();
  const $loader = document.getElementById('ar-loader');
  const $err    = document.getElementById('ar-error');
  const $res    = document.getElementById('ar-result');

  $err.classList.add('hidden');
  $res.classList.add('hidden');

  if (!url && !file) {
    $err.classList.remove('hidden');
    $err.textContent = 'Please paste a PDF URL or upload a PDF.';
    return;
  }

  $loader.classList.remove('hidden');

  try {
    const fd = new FormData();
    if (file) fd.append('file', file);
    if (url) fd.append('url', url);
    if (hint) fd.append('company_hint', hint);

    const r = await fetch('/api/annual_report', { method: 'POST', body: fd });
    const data = await r.json();
    $loader.classList.add('hidden');

    if (!r.ok) {
      $err.classList.remove('hidden');
      $err.textContent = data.detail || `Request failed (HTTP ${r.status}).`;
      return;
    }
    renderReport(data);
    $res.classList.remove('hidden');
    $res.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    $loader.classList.add('hidden');
    $err.classList.remove('hidden');
    $err.textContent = `Unexpected error: ${e.message}`;
  }
}

function renderReport(data) {
  const a = data.analysis || {};
  const meta = data.pdf_meta || {};
  const src = data.source || '';

  document.getElementById('ar-company').textContent =
    a.company_hint || 'Annual report analysis';
  document.getElementById('ar-source').textContent =
    `${meta.n_pages_read || 0} / ${meta.n_pages || '?'} pages read · source: ${src}`;
  document.getElementById('ar-sec-count').textContent =
    `${a.summary?.sections_found ?? 0} / ${a.summary?.sections_total ?? 0}`;

  // Top numbers
  const $num = document.getElementById('ar-numbers');
  const nums = a.top_numbers || [];
  if (!nums.length) {
    $num.innerHTML = `<div class="muted">We could not heuristically find headline numbers. They're usually inside scanned tables, which our text extractor misses. Open the report's "Financial Highlights" page yourself.</div>`;
  } else {
    $num.innerHTML = nums.map(n => `
      <div class="health-cell">
        <div class="top">
          <div class="name">${n.label}</div>
          <span class="badge badge-na mono">${n.value}</span>
        </div>
        <div class="finding">${n.meaning}</div>
      </div>
    `).join('');
  }

  // Sections found — each as a step card
  const $sec = document.getElementById('ar-sections');
  const found = a.sections_found || [];
  if (!found.length) {
    $sec.innerHTML = `<div class="muted">We could not detect any standard sections in this PDF. It might be a scanned image or a non-standard layout.</div>`;
  } else {
    $sec.innerHTML = found.map((s, i) => `
      <div class="step">
        <div class="step-head">
          <div class="step-num">${s.icon}</div>
          <h4>${s.title}</h4>
        </div>
        <p class="muted" style="font-size: 13px; margin: 4px 0 10px;"><strong>What this section is:</strong> ${s.what_it_is}</p>
        <p class="muted" style="font-size: 13px; margin: 0 0 10px;"><strong>Why pros read it:</strong> ${s.why_pros_read_it}</p>

        <div class="summary-grid" style="margin: 10px 0;">
          <div class="summary-cell good">
            <h5>🟢 Green flags to look for</h5>
            <ul>${s.green_flags.map(f => `<li>${f}</li>`).join('')}</ul>
          </div>
          <div class="summary-cell risky">
            <h5>🔴 Red flags to look for</h5>
            <ul>${s.red_flags.map(f => `<li>${f}</li>`).join('')}</ul>
          </div>
        </div>

        <details>
          <summary style="cursor: pointer; color: var(--accent); font-size: 13px; font-weight: 600; padding: 6px 0;">
            📖 Show preview from this report
          </summary>
          <div class="obs" style="white-space: pre-wrap; font-size: 13px; line-height: 1.6; margin-top: 8px; max-height: 360px; overflow-y: auto;">${escapeHtml(s.preview || '')}</div>
        </details>
      </div>
    `).join('');
  }

  // Sections missing — quick reference grid
  const $miss = document.getElementById('ar-missing');
  const missing = a.sections_missing || [];
  if (!missing.length) {
    $miss.innerHTML = `<div class="muted" style="grid-column: 1 / -1;">✅ All standard sections were detected.</div>`;
  } else {
    $miss.innerHTML = missing.map(m => `
      <div class="health-cell">
        <div class="top">
          <div class="name">${m.icon} ${m.title}</div>
          <span class="badge badge-na">Not found</span>
        </div>
        <div class="finding">${m.what_it_is}</div>
        <div class="why"><strong>Why it usually exists:</strong> ${m.why_pros_read_it}</div>
      </div>
    `).join('');
  }

  document.getElementById('ar-learned').textContent = a.what_you_learned || '';
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
