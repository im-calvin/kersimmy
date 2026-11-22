(() => {
  const key = 'translation-reader:theme';
  const system = matchMedia('(prefers-color-scheme: dark)');
  function readTheme() {
    try {
      const saved = window.localStorage.getItem(key);
      if (saved === 'light' || saved === 'dark') return saved;
    } catch {}
    return 'system';
  }

  let preference = readTheme();
  const root = document.documentElement;
  function applyTheme() {
    const dark = preference === 'system' ? system.matches : preference === 'dark';
    root.dataset.theme = dark ? 'dark' : 'light';
    const label = dark ? 'Switch to light mode' : 'Switch to dark mode';
    for (const button of document.querySelectorAll('.theme-toggle')) {
      button.textContent = dark ? '☀\uFE0E' : '☾';
      button.setAttribute('aria-label', label);
      button.title = label;
    }
  }

  applyTheme();
  document.addEventListener('DOMContentLoaded', applyTheme);
  system.addEventListener('change', applyTheme);
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = readTheme();
    applyTheme();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.theme-toggle')) return;
    preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { window.localStorage.setItem(key, preference); } catch {}
    applyTheme();
  });
})();
