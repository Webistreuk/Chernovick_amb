(function () {
  const QUEUE_KEY = 'pending_forms';

  function getQueue() {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
  }
  function saveQueue(q) {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  }

  function updateOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (!banner) return;
    banner.classList.toggle('visible', !navigator.onLine);
  }
  window.addEventListener('online', updateOfflineBanner);
  window.addEventListener('offline', updateOfflineBanner);
  updateOfflineBanner();

  document.querySelectorAll('form[data-offline-queue]').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (navigator.onLine) return;

      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      const queue = getQueue();
      queue.push({
        url: form.action,
        method: form.method || 'POST',
        data,
        client_id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
      });
      saveQueue(queue);
      showFlash('Сохранено локально. Отправим, когда появится связь.', 'warning');
      form.reset();
    });
  });

  window.addEventListener('online', async () => {
    const queue = getQueue();
    if (!queue.length) return;

    const remaining = [];
    for (const item of queue) {
      try {
        const res = await fetch(item.url, {
          method: item.method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...item.data, client_id: item.client_id }),
        });
        if (!res.ok) throw new Error('fail');
      } catch {
        remaining.push(item);
      }
    }
    saveQueue(remaining);

    if (!remaining.length) {
      showFlash(`Отправлено ${queue.length} записей.`, 'success');
    } else {
      showFlash(`Не удалось отправить ${remaining.length} записей.`, 'danger');
    }
  });
})();