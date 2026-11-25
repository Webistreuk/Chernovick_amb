(function () {
  const FIELD_KEY = "search_field";

  const toggle     = document.getElementById("field-toggle");
  const menu       = document.getElementById("field-menu");
  const label      = document.getElementById("field-label");
  const input      = document.getElementById("field-input");
  const search     = document.getElementById("calls-search");
  const results    = document.getElementById("results");
  const refreshBtn = document.getElementById("refresh-btn");
  const maskView   = document.getElementById("phone-mask-view");
  const inputWrap  = document.getElementById("search-input-wrap");
  const sortBtn    = document.getElementById("sort-distance-btn");
  const viewInput  = document.getElementById("view-input");
  const mapToggle  = document.getElementById("map-toggle-btn");
  const contentArea = document.getElementById("content-area");
  const mapEl      = document.getElementById("map");

  if (!toggle || !menu || !input || !results) return;

  const labels = {
    name:    "Поиск по ФИО",
    address: "Поиск по адресу",
    phone:   "Поиск по номеру телефона",
  };

  let currentView = viewInput ? viewInput.value : "all";
  let mapMode = false;

  const activeCallId = mapEl ? (mapEl.dataset.activeCallId || "") : "";

  // ================= МАСКА ТЕЛЕФОНА =================
  const PHONE_TEMPLATE = "XXX XXX-XX-XX";
  const MAX_DIGITS = 10;
  let phoneDigits = "";

  function renderMaskHTML() {
    let html = "+7 ";
    let di = 0;
    for (let i = 0; i < PHONE_TEMPLATE.length; i++) {
      const ch = PHONE_TEMPLATE[i];
      if (ch === "X") {
        if (di < phoneDigits.length) html += phoneDigits[di];
        else html += '<span class="phone-x">X</span>';
        di++;
      } else html += ch;
    }
    return html;
  }

  function updateMaskView() {
    if (maskView) maskView.innerHTML = renderMaskHTML();
  }

  function setPhoneMode(on) {
    if (on) {
      phoneDigits = "";
      search.value = "";
      search.placeholder = "";
      search.inputMode = "numeric";
      search.setAttribute("autocomplete", "off");
      if (maskView) maskView.hidden = false;
      if (inputWrap) inputWrap.classList.add("phone-mode");
      updateMaskView();
    } else {
      phoneDigits = "";
      search.value = "";
      search.placeholder = "Поиск";
      search.removeAttribute("inputMode");
      search.removeAttribute("autocomplete");
      if (maskView) {
        maskView.hidden = true;
        maskView.innerHTML = "";
      }
      if (inputWrap) inputWrap.classList.remove("phone-mode");
    }
  }
  // ==================================================

  const saved = localStorage.getItem(FIELD_KEY);
  if (saved && labels[saved]) {
    const url = new URL(window.location.href);
    if (!url.searchParams.get("field") && input.value !== saved) {
      input.value = saved;
      label.textContent = labels[saved];
    }
  }

  if (input.value === "phone") {
    const initialQ = (search.value || "").replace(/\D/g, "");
    setPhoneMode(true);
    if (initialQ) {
      let d = initialQ;
      if (d.startsWith("7")) d = d.slice(1);
      phoneDigits = d.slice(0, MAX_DIGITS);
      search.value = phoneDigits;
      updateMaskView();
    }
  }

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
  });

  menu.querySelectorAll("button[data-field]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const field = btn.dataset.field;
      const wasPhone = input.value === "phone";
      input.value = field;
      label.textContent = labels[field];
      localStorage.setItem(FIELD_KEY, field);
      menu.hidden = true;

      if (field === "phone") setPhoneMode(true);
      else if (wasPhone) setPhoneMode(false);

      if (mapMode) loadCallPoints();
      else runSearch(1);
    });
  });

  document.addEventListener("click", (e) => {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== toggle) {
      menu.hidden = true;
    }
  });

  search.addEventListener("beforeinput", (e) => {
    if (input.value !== "phone") return;
    if (e.inputType === "insertText" && !/^\d$/.test(e.data || "")) {
      e.preventDefault();
      return;
    }
    if (e.inputType === "insertFromPaste") {
      const pasted = (e.dataTransfer && e.dataTransfer.getData("text")) || "";
      const digits = pasted.replace(/\D/g, "");
      if (!digits) { e.preventDefault(); return; }
      e.preventDefault();
      for (const d of digits) {
        if (phoneDigits.length >= MAX_DIGITS) break;
        phoneDigits += d;
      }
      search.value = phoneDigits;
      updateMaskView();
      if (mapMode) loadCallPoints();
      else runSearch(1);
      return;
    }
    if (e.inputType === "insertText" && phoneDigits.length >= MAX_DIGITS) {
      e.preventDefault();
    }
  });

  search.addEventListener("input", () => {
    if (input.value !== "phone") {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        if (mapMode) loadCallPoints();
        else runSearch(1);
      }, 300);
      return;
    }
    const raw = search.value.replace(/\D/g, "");
    let digits = raw;
    if (digits.startsWith("7")) digits = digits.slice(1);
    phoneDigits = digits.slice(0, MAX_DIGITS);
    if (search.value !== phoneDigits) search.value = phoneDigits;
    updateMaskView();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      if (mapMode) loadCallPoints();
      else runSearch(1);
    }, 300);
  });

  search.addEventListener("keydown", (e) => {
    if (input.value !== "phone") return;
    if (e.key === "Backspace" || e.key === "Delete") {
      e.preventDefault();
      if (phoneDigits.length > 0) {
        phoneDigits = phoneDigits.slice(0, -1);
        search.value = phoneDigits;
        updateMaskView();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          if (mapMode) loadCallPoints();
          else runSearch(1);
        }, 300);
      }
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      clearTimeout(debounceTimer);
      if (mapMode) loadCallPoints();
      else runSearch(1);
    }
  });

  search.addEventListener("keydown", (e) => {
    if (input.value === "phone") return;
    if (e.key === "Enter") {
      e.preventDefault();
      clearTimeout(debounceTimer);
      if (mapMode) loadCallPoints();
      else runSearch(1);
    }
  });

  if (sortBtn) {
    sortBtn.addEventListener("click", () => {
      currentView = (currentView === "nearest") ? "all" : "nearest";
      sortBtn.classList.toggle("btn-active", currentView === "nearest");
      if (viewInput) viewInput.value = currentView;

      if (mapMode) loadCallPoints();
      else runSearch(1);
    });
  }

  let debounceTimer = null;
  let abortController = null;

  async function runSearch(page = 1) {
    const field = input.value;
    let q;
    if (field === "phone") q = phoneDigits;
    else q = search.value.trim();

    if (abortController) abortController.abort();
    abortController = new AbortController();

    const params = new URLSearchParams({ q, field, page, view: currentView });

    try {
      const res = await fetch("/search?" + params.toString(), {
        signal: abortController.signal,
      });
      if (!res.ok) return;
      const html = await res.text();
      results.innerHTML = html;
      bindPagination();
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    }
  }

  function bindPagination() {
    const pag = document.getElementById("pagination");
    if (!pag) return;
    pag.querySelectorAll(".pagination-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const page = parseInt(a.dataset.page, 10) || 1;
        runSearch(page);
      });
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", (e) => {
      e.preventDefault();
      localStorage.removeItem(FIELD_KEY);
      window.location.href = "/";
    });
  }

  // ================= КАРТА =================
  let map = null;
  let callMarkers = [];
  let ambulanceMarker = null;
  let refreshTimer = null;

  function setMapMode(on) {
    mapMode = on;
    if (contentArea) contentArea.style.display = on ? "none" : "";
    if (mapEl) mapEl.style.display = on ? "block" : "none";

    if (mapToggle) {
      mapToggle.classList.toggle("btn-active", on);
      const state = mapToggle.querySelector(".map-toggle-state");
      if (state) state.textContent = on ? "[on]" : "[off]";
    }

    if (on) {
      if (currentView === "nearest") {
        currentView = "all";
        if (sortBtn) sortBtn.classList.remove("btn-active");
        if (viewInput) viewInput.value = "all";
      }
      initMap();
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  }

  if (mapToggle) {
    mapToggle.addEventListener("click", () => setMapMode(!mapMode));
  }

  function initMap() {
    if (!mapEl || typeof L === "undefined") return;

    if (!map) {
      map = L.map(mapEl).setView([43.585, 39.723], 12);
      // OSM-тайлы напрямую с CDN
      L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors © CARTO",
      }).addTo(map);
      startGeolocation();
    }

    setTimeout(() => map.invalidateSize(), 100);
    loadCallPoints();
  }

  async function loadCallPoints() {
    try {
      const res = await fetch("/api/map_points?view=" + encodeURIComponent(currentView));
      if (!res.ok) return;
      const points = await res.json();
      renderCallPoints(points);
    } catch (e) {
      console.error("Не удалось загрузить точки вызовов", e);
    }
  }

  function renderCallPoints(points) {
    callMarkers.forEach((m) => map.removeLayer(m));
    callMarkers = [];

    points.forEach((p) => {
      const marker = L.marker([p.lat, p.lng]).addTo(map);

      marker.on("mousedown", (e) => L.DomEvent.stopPropagation(e));
      marker.on("dblclick", (e) => L.DomEvent.stopPropagation(e));

      const distText = (p.distance_km != null)
        ? `<br>🚑 ≈ ${p.distance_km} км от скорой`
        : "";

      const infoHtml = `
        <div class="map-popup">
          <strong>${p.patient_name}</strong><br>
          ${p.address}${distText}
          <div class="map-popup-hint">Двойной клик — взять вызов</div>
        </div>
      `;

      const hasActive = activeCallId !== "";
      const isThisActive = String(activeCallId) === String(p.id);
      const blockTaking = hasActive && !isThisActive;

      const confirmHtml = blockTaking
        ? `
          <div class="map-popup map-popup-confirm">
            <div class="map-popup-blocked">Уже есть текущий вызов</div>
            <strong>${p.patient_name}</strong><br>
            ${p.address}
            <div class="map-popup-actions">
              <button type="button" class="map-popup-btn map-popup-yes" disabled>Да</button>
              <button type="button" class="map-popup-btn map-popup-no" disabled>Нет</button>
            </div>
          </div>
        `
        : `
          <div class="map-popup map-popup-confirm">
            <strong>Взять вызов?</strong><br>
            ${p.patient_name}<br>
            ${p.address}
            <div class="map-popup-actions">
              <button type="button" class="map-popup-btn map-popup-yes"
                      data-call-id="${p.id}">Да</button>
              <button type="button" class="map-popup-btn map-popup-no">Нет</button>
            </div>
          </div>
        `;

      marker.bindPopup(infoHtml);

      let clickTimer = null;

      marker.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        if (clickTimer) {
          clearTimeout(clickTimer);
          clickTimer = null;
          marker.setPopupContent(confirmHtml);
          marker.openPopup();
        } else {
          clickTimer = setTimeout(() => { clickTimer = null; }, 300);
        }
      });

      marker.on("popupopen", (e) => {
        const popupEl = e.popup.getElement();
        if (!popupEl) return;

        const yesBtn = popupEl.querySelector(".map-popup-yes");
        const noBtn = popupEl.querySelector(".map-popup-no");

        if (yesBtn && !yesBtn.disabled) {
          yesBtn.addEventListener("click", () => {
            const callId = yesBtn.dataset.callId;
            const form = document.createElement("form");
            form.method = "POST";
            form.action = `/call/${callId}/accept`;
            document.body.appendChild(form);
            form.submit();
          });
        }

        if (noBtn && !noBtn.disabled) {
          noBtn.addEventListener("click", () => map.closePopup());
        }
      });

      callMarkers.push(marker);
    });
  }

  function startGeolocation() {
    if (!navigator.geolocation) return;

    navigator.geolocation.watchPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;

        if (!ambulanceMarker) {
          const ambulanceIcon = L.divIcon({
            className: "ambulance-marker",
            html: "🚑",
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });
          ambulanceMarker = L.marker([lat, lng], { icon: ambulanceIcon }).addTo(map);
          ambulanceMarker.bindPopup("🚑 Машина скорой помощи");
        } else {
          ambulanceMarker.setLatLng([lat, lng]);
        }
      },
      (err) => console.warn("Геолокация:", err.message),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    refreshTimer = setInterval(() => {
      if (mapMode) loadCallPoints();
    }, 8000);
  }

  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }
  // =====================================================

  bindPagination();

  if (mapEl && mapEl.dataset.initMap === "1" && !mapMode) {
    setMapMode(true);
  }
})();