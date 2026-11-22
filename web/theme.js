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
  function applyTheme() {
    document.documentElement.dataset.theme = preference === 'system'
      ? (system.matches ? 'dark' : 'light') : preference;
    for (const control of document.querySelectorAll('[data-theme-setting]')) control.value = preference;
  }

  applyTheme();
  document.addEventListener('DOMContentLoaded', applyTheme);
  system.addEventListener('change', applyTheme);
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = readTheme();
    applyTheme();
  });
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-theme-setting]')) return;
    preference = event.target.value;
    try { window.localStorage.setItem(key, preference); } catch {}
    applyTheme();
  });
})();
