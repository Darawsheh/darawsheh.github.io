(() => {
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  const themes = ['system', 'light', 'dark'];
  const saved = localStorage.getItem('portfolio-theme');

  if (saved && themes.includes(saved)) root.dataset.theme = saved;

  const updateLabel = () => {
    const current = root.dataset.theme || 'system';
    button.textContent = `Theme: ${current}`;
    button.setAttribute('aria-label', `Current theme is ${current}. Activate to change theme.`);
  };

  button.addEventListener('click', () => {
    const current = root.dataset.theme || 'system';
    const next = themes[(themes.indexOf(current) + 1) % themes.length];
    root.dataset.theme = next;
    localStorage.setItem('portfolio-theme', next);
    updateLabel();
  });

  document.getElementById('year').textContent = new Date().getFullYear();
  updateLabel();
})();
