try {
  const prefs = JSON.parse(localStorage.getItem('probability-reading-v1') || '{}');
  if (['comfortable', 'large', 'largest'].includes(prefs.size)) document.documentElement.dataset.size = prefs.size;
  if (['high', 'soft'].includes(prefs.tone)) document.documentElement.dataset.tone = prefs.tone;
} catch (_) { /* Reading remains available when browser storage is unavailable. */ }
