function updateNetStatus() {
  const el = document.getElementById("net-status");
  if (!el) return;
  if (navigator.onLine) {
    el.className = "net-badge net-online";
    el.textContent = "🟢 Онлайн";
  } else {
    el.className = "net-badge net-offline";
    el.textContent = "🔴 Офлайн";
  }
}
window.addEventListener("online", updateNetStatus);
window.addEventListener("offline", updateNetStatus);
updateNetStatus();

function showFlash(text, type = "info") {
  const area = document.getElementById("flash-area");
  if (!area) return;
  const div = document.createElement("div");
  div.className = `notice notice-${type}`;
  div.textContent = text;
  area.appendChild(div);
  setTimeout(() => div.remove(), 5000);
}

// Регистрация Service Worker для кэша тайлов OSM
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .catch((e) => console.warn("SW register:", e));
  });
}