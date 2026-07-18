(function () {
  const FAVORITES_PATH = "__favorites__";

  const grid = document.getElementById("grid");
  const emptyState = document.getElementById("empty-state");
  const emptyTitle = document.getElementById("empty-title");
  const emptySub = document.getElementById("empty-sub");
  const breadcrumbsEl = document.getElementById("breadcrumbs");
  const brand = document.querySelector(".brand");
  const backBtn = document.getElementById("back-btn");
  const toast = document.getElementById("toast");

  const themeBtn = document.getElementById("theme-btn");
  const favoritesBtn = document.getElementById("favorites-btn");
  const settingsBtn = document.getElementById("settings-btn");
  const settingsModal = document.getElementById("settings-modal");
  const settingsClose = document.getElementById("settings-close");
  const cacheInfoText = document.getElementById("cache-info-text");
  const cacheProgressWrap = document.getElementById("cache-progress-wrap");
  const cacheProgressFill = document.getElementById("cache-progress-fill");
  const cacheProgressLabel = document.getElementById("cache-progress-label");
  const cacheBuildBtn = document.getElementById("cache-build-btn");
  const cacheClearBtn = document.getElementById("cache-clear-btn");

  const lightbox = document.getElementById("lightbox");
  const lbImage = document.getElementById("lb-image");
  const lbCounter = document.getElementById("lb-counter");
  const lbClose = document.getElementById("lb-close");
  const lbPrev = document.getElementById("lb-prev");
  const lbNext = document.getElementById("lb-next");
  const lbFavBtn = document.getElementById("lb-fav-btn");
  const lbInfoBtn = document.getElementById("lb-info-btn");

  const infoPanel = document.getElementById("info-panel");
  const infoClose = document.getElementById("info-close");
  const infoFilename = document.getElementById("info-filename");
  const infoList = document.getElementById("info-list");
  const infoMapEl = document.getElementById("info-map");

  let currentPhotos = [];
  let currentPhotoIndex = 0;
  let leafletMap = null;
  let leafletMarker = null;

  // ---------------- Pagination / infinite scroll ----------------

  const PAGE_SIZE = 300;
  const scrollSentinel = document.getElementById("scroll-sentinel");
  let currentBrowsePath = "";
  let currentOffset = 0;
  let hasMore = false;
  let isLoadingMore = false;

  const scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        loadMoreItems();
      }
    },
    { rootMargin: "600px" } // start loading well before the user actually hits the bottom
  );

  function setupInfiniteScroll() {
    scrollSentinel.hidden = false;
    scrollObserver.observe(scrollSentinel);
  }

  function teardownInfiniteScroll() {
    scrollSentinel.hidden = true;
    scrollObserver.unobserve(scrollSentinel);
  }

  async function loadMoreItems() {
    if (isLoadingMore || !hasMore) return;
    isLoadingMore = true;
    try {
      const res = await fetch(
        `/api/browse?path=${encodeURIComponent(currentBrowsePath)}&offset=${currentOffset}&limit=${PAGE_SIZE}`
      );
      if (!res.ok) return;
      const data = await res.json();

      if (data.type === "folders") {
        data.items.forEach((item) => grid.appendChild(folderTile(item)));
      } else if (data.type === "photos") {
        const startIndex = currentPhotos.length;
        currentPhotos = currentPhotos.concat(data.items);
        data.items.forEach((item, i) => grid.appendChild(photoTile(item, startIndex + i)));
      }

      currentOffset += data.items.length;
      hasMore = !!data.has_more;
      if (!hasMore) teardownInfiniteScroll();
    } finally {
      isLoadingMore = false;
    }
  }

  // ---------------- Theme ----------------

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("album-theme", theme);
    themeBtn.textContent = theme === "light" ? "☀" : "◐";
  }

  themeBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(current === "light" ? "dark" : "light");
  });
  applyTheme(document.documentElement.getAttribute("data-theme") || "dark");

  favoritesBtn.addEventListener("click", () => loadPath(FAVORITES_PATH));

  // ---------------- Navigation ----------------

  function pathFromLocation() {
    const params = new URLSearchParams(window.location.search);
    return params.get("path") || "";
  }

  async function loadPath(path, pushState = true) {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}&offset=0&limit=${PAGE_SIZE}`);
    if (!res.ok) {
      grid.innerHTML = "";
      teardownInfiniteScroll();
      showEmpty("Niets gevonden", "Deze locatie bestaat niet (meer).");
      return;
    }
    const data = await res.json();

    if (pushState) {
      const url = data.path ? `?path=${encodeURIComponent(data.path)}` : window.location.pathname;
      history.pushState({ path: data.path }, "", url);
    }

    renderBreadcrumbs(data.breadcrumbs, data.path === FAVORITES_PATH);
    updateBackButton(data);
    render(data);
  }

  function updateBackButton(data) {
    if (data.path === FAVORITES_PATH) {
      backBtn.hidden = false;
      backBtn.onclick = () => loadPath("");
      return;
    }
    if (!data.breadcrumbs || data.breadcrumbs.length === 0) {
      // We're already at the top-level overview, nothing to go back to.
      backBtn.hidden = true;
      backBtn.onclick = null;
      return;
    }
    const parentPath =
      data.breadcrumbs.length >= 2 ? data.breadcrumbs[data.breadcrumbs.length - 2].path : "";
    backBtn.hidden = false;
    backBtn.onclick = () => loadPath(parentPath);
  }

  function renderBreadcrumbs(crumbs, isFavorites) {
    breadcrumbsEl.innerHTML = "";
    crumbs.forEach((c, i) => {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "•";
      breadcrumbsEl.appendChild(sep);

      const el = document.createElement("span");
      el.className = "crumb" + (i === crumbs.length - 1 ? " current" : "");
      el.textContent = c.name;
      if (!isFavorites) {
        el.addEventListener("click", () => loadPath(c.path));
      }
      breadcrumbsEl.appendChild(el);
    });
  }

  function showEmpty(title, sub) {
    emptyTitle.textContent = title;
    emptySub.textContent = sub;
    emptyState.hidden = false;
  }

  function render(data) {
    grid.innerHTML = "";
    emptyState.hidden = true;
    currentPhotos = [];
    teardownInfiniteScroll();

    currentBrowsePath = data.path;
    currentOffset = data.items.length;
    hasMore = !!data.has_more;

    if (data.type === "folders") {
      data.items.forEach((item) => grid.appendChild(folderTile(item)));
    } else if (data.type === "photos") {
      currentPhotos = data.items.slice();
      if (data.items.length === 0 && data.path === FAVORITES_PATH) {
        showEmpty("Nog geen favorieten", "Klik op het hartje bij een foto om 'm hier te laten verschijnen.");
      } else {
        data.items.forEach((item, i) => grid.appendChild(photoTile(item, i)));
      }
    } else {
      showEmpty("Niets te zien hier", "Deze map bevat geen submappen of foto's.");
    }

    if (hasMore) {
      setupInfiniteScroll();
    }
  }

  function folderTile(item) {
    const tile = document.createElement("div");
    tile.className = "tile folder";
    tile.tabIndex = 0;

    if (item.cover) {
      const img = document.createElement("img");
      img.src = `/api/thumbnail?path=${encodeURIComponent(item.cover)}`;
      img.loading = "lazy";
      img.alt = item.name;
      tile.appendChild(img);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "cover-placeholder";
      placeholder.textContent = "◍";
      tile.appendChild(placeholder);
    }

    const label = document.createElement("div");
    label.className = "label";
    label.textContent = item.name;
    tile.appendChild(label);

    const open = () => loadPath(item.path);
    tile.addEventListener("click", open);
    tile.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") open();
    });

    return tile;
  }

  function photoTile(item, index) {
    const tile = document.createElement("div");
    tile.className = "tile photo";
    tile.tabIndex = 0;
    tile.dataset.path = item.path;

    const img = document.createElement("img");
    img.src = `/api/thumbnail?path=${encodeURIComponent(item.path)}`;
    img.loading = "lazy";
    img.alt = item.name;
    tile.appendChild(img);

    const favBtn = document.createElement("button");
    favBtn.className = "tile-fav-btn" + (item.favorite ? " active" : "");
    favBtn.textContent = item.favorite ? "♥" : "♡";
    favBtn.setAttribute("aria-label", "Favoriet");
    favBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleFavorite(item.path, favBtn);
    });
    tile.appendChild(favBtn);

    const open = () => openLightbox(index);
    tile.addEventListener("click", open);
    tile.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") open();
    });

    return tile;
  }

  async function toggleFavorite(path, buttonEl) {
    const res = await fetch("/api/favorites/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) {
      showToast("Kon favoriet niet opslaan — probeer opnieuw.");
      return;
    }
    const data = await res.json();

    // Update every button that refers to this photo (grid + optionally the lightbox)
    document.querySelectorAll(`[data-path="${CSS.escape(path)}"] .tile-fav-btn`).forEach((btn) => {
      setFavButtonState(btn, data.favorite);
    });
    if (buttonEl) setFavButtonState(buttonEl, data.favorite);
    setFavButtonState(lbFavBtn, currentPhotos[currentPhotoIndex] && currentPhotos[currentPhotoIndex].path === path ? data.favorite : lbFavBtn.classList.contains("active"));

    const item = currentPhotos.find((p) => p.path === path);
    if (item) item.favorite = data.favorite;

    showToast(data.favorite ? "Toegevoegd aan favorieten" : "Verwijderd uit favorieten", data.favorite);

    // If we're in the favorites overview and a photo gets "unfavorited",
    // make it disappear immediately.
    if (!data.favorite && pathFromLocation() === FAVORITES_PATH) {
      loadPath(FAVORITES_PATH, false);
    }
  }

  function setFavButtonState(btn, isFavorite) {
    if (!btn) return;
    btn.classList.toggle("active", isFavorite);
    // Only the heart on the tiles swaps between the ♡/♥ glyphs; the button in
    // the viewer (lb-fav) always keeps the same glyph and only changes color.
    if (btn.classList.contains("tile-fav-btn")) {
      btn.textContent = isFavorite ? "♥" : "♡";
    }
    btn.classList.remove("pulse");
    // Force a reflow so the animation still plays on rapid repeated clicks.
    void btn.offsetWidth;
    btn.classList.add("pulse");
  }

  let toastTimer = null;
  function showToast(message, isFavorite) {
    clearTimeout(toastTimer);
    toast.innerHTML = "";
    if (isFavorite === true) {
      const heart = document.createElement("span");
      heart.className = "toast-heart";
      heart.textContent = "♥";
      toast.appendChild(heart);
    }
    toast.appendChild(document.createTextNode(message));
    toast.hidden = false;
    toast.classList.remove("hide");
    toastTimer = setTimeout(() => {
      toast.classList.add("hide");
      setTimeout(() => {
        toast.hidden = true;
      }, 250);
    }, 1800);
  }

  // ---------------- Lightbox ----------------

  function openLightbox(index) {
    currentPhotoIndex = index;
    showCurrentPhoto();
    lightbox.hidden = false;
  }

  function showCurrentPhoto() {
    const photo = currentPhotos[currentPhotoIndex];
    lbImage.src = `/api/image?path=${encodeURIComponent(photo.path)}`;
    lbImage.alt = photo.name;
    lbCounter.textContent = `${currentPhotoIndex + 1} / ${currentPhotos.length}`;
    lbFavBtn.classList.toggle("active", !!photo.favorite);

    if (!infoPanel.hidden) {
      loadExifInto(photo.path);
    }
  }

  function closeLightbox() {
    lightbox.hidden = true;
    lbImage.src = "";
    infoPanel.hidden = true;
  }

  function showNext() {
    currentPhotoIndex = (currentPhotoIndex + 1) % currentPhotos.length;
    showCurrentPhoto();
  }

  function showPrev() {
    currentPhotoIndex = (currentPhotoIndex - 1 + currentPhotos.length) % currentPhotos.length;
    showCurrentPhoto();
  }

  lbClose.addEventListener("click", closeLightbox);
  lbNext.addEventListener("click", showNext);
  lbPrev.addEventListener("click", showPrev);
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  lbFavBtn.addEventListener("click", () => {
    const photo = currentPhotos[currentPhotoIndex];
    if (photo) toggleFavorite(photo.path, null);
  });

  lbInfoBtn.addEventListener("click", () => {
    const photo = currentPhotos[currentPhotoIndex];
    if (!photo) return;
    if (infoPanel.hidden) {
      infoPanel.hidden = false;
      loadExifInto(photo.path);
    } else {
      infoPanel.hidden = true;
    }
  });

  infoClose.addEventListener("click", () => {
    infoPanel.hidden = true;
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !settingsModal.hidden) {
      closeSettings();
      return;
    }
    if (lightbox.hidden) return;
    if (e.key === "Escape") {
      if (!infoPanel.hidden) {
        infoPanel.hidden = true;
      } else {
        closeLightbox();
      }
    }
    if (e.key === "ArrowRight") showNext();
    if (e.key === "ArrowLeft") showPrev();
  });

  // ---------------- EXIF / info panel ----------------

  const EXIF_LABELS = [
    ["camera", "Camera"],
    ["lens", "Lens"],
    ["date_taken", "Datum"],
    ["exposure", "Sluitertijd"],
    ["fnumber", "Diafragma"],
    ["iso", "ISO"],
    ["focal_length", "Brandpuntsafstand"],
  ];

  async function loadExifInto(path) {
    infoFilename.textContent = "Laden...";
    infoList.innerHTML = "";
    infoMapEl.hidden = true;

    const res = await fetch(`/api/exif?path=${encodeURIComponent(path)}`);
    if (!res.ok) {
      infoFilename.textContent = path.split("/").pop();
      return;
    }
    const data = await res.json();

    infoFilename.textContent = data.filename;

    if (data.width && data.height) {
      addInfoRow("Afmetingen", `${data.width} × ${data.height}px`);
    }
    EXIF_LABELS.forEach(([key, label]) => {
      if (data[key]) addInfoRow(label, data[key]);
    });
    if (!infoList.children.length) {
      addInfoRow("Metadata", "Geen EXIF-gegevens gevonden in dit bestand.");
    }

    if (data.gps && typeof data.gps.lat === "number") {
      infoMapEl.hidden = false;
      showOnMap(data.gps.lat, data.gps.lon);
    }
  }

  function addInfoRow(label, value) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    infoList.appendChild(dt);
    infoList.appendChild(dd);
  }

  function showOnMap(lat, lon) {
    if (typeof L === "undefined") return;

    if (!leafletMap) {
      leafletMap = L.map(infoMapEl).setView([lat, lon], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(leafletMap);
      leafletMarker = L.marker([lat, lon]).addTo(leafletMap);
    } else {
      leafletMap.setView([lat, lon], 13);
      leafletMarker.setLatLng([lat, lon]);
    }
    // The map container was hidden until just now (display:none), so Leaflet
    // needs to recalculate its size now that it's visible.
    setTimeout(() => leafletMap.invalidateSize(), 50);
  }

  // ---------------- Settings / bulk cache ----------------

  let cachePollTimer = null;

  function formatBytes(bytes) {
    if (!bytes) return "0 MB";
    const mb = bytes / (1024 * 1024);
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
  }

  async function refreshCacheInfo() {
    try {
      const res = await fetch("/api/cache/info");
      if (!res.ok) throw new Error("info failed");
      const data = await res.json();
      cacheInfoText.textContent =
        `${data.cached_files} van de ${data.total_images} foto's hebben al een thumbnail ` +
        `(${formatBytes(data.cache_size_bytes)} cache).`;
    } catch {
      cacheInfoText.textContent = "Kon cache-informatie niet ophalen.";
    }
  }

  function renderCacheStatus(status) {
    if (status.status === "running") {
      cacheProgressWrap.hidden = false;
      const pct = status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;
      cacheProgressFill.style.width = `${pct}%`;
      cacheProgressLabel.textContent = status.message
        ? status.message
        : `${status.processed} / ${status.total} foto's verwerkt`;
      cacheBuildBtn.disabled = true;
      cacheClearBtn.disabled = true;
    } else {
      cacheBuildBtn.disabled = false;
      cacheClearBtn.disabled = false;
      if (status.status === "done" && status.processed > 0) {
        cacheProgressWrap.hidden = false;
        cacheProgressFill.style.width = "100%";
        const skippedText = status.skipped ? ` (${status.skipped} overgeslagen)` : "";
        cacheProgressLabel.textContent = `Klaar — ${status.processed} foto's verwerkt${skippedText}.`;
      } else if (status.status === "error") {
        cacheProgressWrap.hidden = false;
        cacheProgressLabel.textContent = `Er ging iets mis: ${status.message || "onbekende fout"}`;
      } else if (status.status === "interrupted") {
        cacheProgressWrap.hidden = false;
        const pct = status.total > 0 ? Math.round((status.processed / status.total) * 100) : 0;
        cacheProgressFill.style.width = `${pct}%`;
        cacheProgressLabel.textContent =
          `Onderbroken na ${status.processed} / ${status.total} foto's (bijv. door een herstart) ` +
          `— klik opnieuw op "Cache nu volledig aanmaken" om verder te gaan.`;
      } else {
        cacheProgressWrap.hidden = true;
      }
    }
  }

  async function pollCacheStatus() {
    try {
      const res = await fetch("/api/cache/status");
      const status = await res.json();
      renderCacheStatus(status);
      if (status.status === "running") {
        cachePollTimer = setTimeout(pollCacheStatus, 1000);
      } else {
        clearTimeout(cachePollTimer);
        refreshCacheInfo();
      }
    } catch {
      clearTimeout(cachePollTimer);
    }
  }

  async function openSettings() {
    settingsModal.hidden = false;
    refreshCacheInfo();
    const res = await fetch("/api/cache/status");
    const status = await res.json();
    renderCacheStatus(status);
    if (status.status === "running") {
      clearTimeout(cachePollTimer);
      pollCacheStatus();
    }
  }

  function closeSettings() {
    settingsModal.hidden = true;
    clearTimeout(cachePollTimer);
  }

  settingsBtn.addEventListener("click", openSettings);
  settingsClose.addEventListener("click", closeSettings);
  settingsModal.addEventListener("click", (e) => {
    if (e.target === settingsModal) closeSettings();
  });

  cacheBuildBtn.addEventListener("click", async () => {
    cacheBuildBtn.disabled = true;
    cacheClearBtn.disabled = true;
    await fetch("/api/cache/start", { method: "POST" });
    clearTimeout(cachePollTimer);
    pollCacheStatus();
  });

  cacheClearBtn.addEventListener("click", async () => {
    if (!confirm("Weet je zeker dat je de cache wilt legen? Thumbnails worden opnieuw aangemaakt zodra je een foto bekijkt.")) {
      return;
    }
    cacheClearBtn.disabled = true;
    try {
      await fetch("/api/cache/clear", { method: "POST" });
      cacheProgressWrap.hidden = true;
      await refreshCacheInfo();
      showToast("Cache geleegd");
    } finally {
      cacheClearBtn.disabled = false;
    }
  });

  // ---------------- Init ----------------

  brand.addEventListener("click", () => loadPath(""));

  window.addEventListener("popstate", (e) => {
    const path = (e.state && e.state.path) || "";
    loadPath(path, false);
  });

  loadPath(pathFromLocation(), false);
})();
