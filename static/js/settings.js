import {
  cacheBuildBtn,
  cacheClearBtn,
  cacheInfoText,
  cacheProgressFill,
  cacheProgressLabel,
  cacheProgressWrap,
  settingsBtn,
  settingsClose,
  settingsModal,
} from "./dom.js";
import { showToast } from "./toast.js";

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

export function closeSettings() {
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
