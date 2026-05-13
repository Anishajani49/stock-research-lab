// Landing page — wire the search box to navigate to the dashboard.
document.addEventListener('DOMContentLoaded', () => {
  bindSearchBox({
    inputId: 'search-input',
    suggestionsId: 'search-suggestions',
    goId: 'search-go',
    onSubmit: (symbol) => {
      window.location.href = `/dashboard?ticker=${encodeURIComponent(symbol)}`;
    },
  });
});
