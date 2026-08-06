(() => {
  const root = document.documentElement;

  const giscusTheme = () => {
    const selected = root.dataset.theme || 'system';
    if (selected === 'system') return 'preferred_color_scheme';
    return selected;
  };

  const syncGiscusTheme = () => {
    const iframe = document.querySelector('iframe.giscus-frame');
    if (!iframe) return;

    iframe.contentWindow.postMessage(
      {
        giscus: {
          setConfig: {
            theme: giscusTheme()
          }
        }
      },
      'https://giscus.app'
    );
  };

  window.addEventListener('message', event => {
    if (event.origin === 'https://giscus.app') syncGiscusTheme();
  });

  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    window.setTimeout(syncGiscusTheme, 0);
  });
})();
