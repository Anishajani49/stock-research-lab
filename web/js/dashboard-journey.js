// =====================================================================
// Dashboard journey controller — runs *alongside* dashboard.js without
// modifying its data flow.
//
//   1.  Strip the initial `.hidden` from data-pane sections (CSS already
//       neutralises any future toggling, but this prevents a first-paint
//       flicker on the panes that started hidden in HTML).
//   2.  Wire the chapter-nav `.tab` buttons to smooth-scroll to the
//       matching chapter section. The legacy listener in dashboard.js
//       still runs (and adds/removes .hidden) — the CSS override makes
//       that have no visual effect.
//   3.  Mark the current chapter active in the nav as the user scrolls.
//   4.  Wire the placeholder "suggestion chips" to load tickers.
// =====================================================================

(function () {
  document.addEventListener('DOMContentLoaded', () => {
    unhidePanes();
    wireChapterNav();
    wireScrollSpy();
    wireSuggestionChips();
  });

  // -------------------------------------------------------------------
  function unhidePanes() {
    document.querySelectorAll('[data-pane]').forEach((p) => p.classList.remove('hidden'));
  }

  // -------------------------------------------------------------------
  // Map every tab button to the chapter section with the matching id.
  // Chapter sections are <article class="cin-chapter" id="chap-<key>">.
  // -------------------------------------------------------------------
  function wireChapterNav() {
    const nav = document.getElementById('tabs');
    if (!nav) return;
    nav.addEventListener('click', (e) => {
      const btn = e.target.closest('.tab');
      if (!btn) return;
      const key = btn.dataset.tab;
      const target = document.getElementById('chap-' + key);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  // -------------------------------------------------------------------
  // Highlight the active chapter as the user scrolls.
  // -------------------------------------------------------------------
  function wireScrollSpy() {
    const chapters = Array.from(document.querySelectorAll('.cin-chapter'));
    const nav = document.getElementById('tabs');
    if (!chapters.length || !nav) return;

    const setActive = (key) => {
      nav.querySelectorAll('.tab').forEach((b) => {
        b.classList.toggle('is-active', b.dataset.tab === key);
        b.classList.toggle('active', b.dataset.tab === key);
      });
    };

    const io = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]) {
        const id = visible[0].target.id;          // e.g. "chap-fundamentals"
        const key = id.replace(/^chap-/, '');
        setActive(key);
      }
    }, { threshold: [0.25, 0.5, 0.75], rootMargin: '-25% 0px -55% 0px' });

    chapters.forEach((c) => io.observe(c));
  }

  // -------------------------------------------------------------------
  function wireSuggestionChips() {
    document.querySelectorAll('.dj-suggestion-chips button[data-ticker]').forEach((b) => {
      b.addEventListener('click', () => {
        const t = b.dataset.ticker;
        const input = document.getElementById('search-input');
        if (input) input.value = t;
        // Reuse the same loader that the search-go button triggers.
        if (typeof loadDashboard === 'function') {
          loadDashboard(t);
        } else {
          window.location.href = '/dashboard?ticker=' + encodeURIComponent(t);
        }
      });
    });
  }
})();
