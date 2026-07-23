import {
  accountInfoText,
  addUserError,
  addUserForm,
  cacheBuildBtn,
  cacheClearBtn,
  cacheInfoText,
  cacheProgressFill,
  cacheProgressLabel,
  cacheProgressWrap,
  currentPasswordInput,
  newPasswordConfirmInput,
  newPasswordInput,
  newUserAdminInput,
  newUserPasswordInput,
  newUsernameInput,
  panelAccount,
  panelCache,
  panelUsers,
  passwordChangeError,
  passwordChangeForm,
  passwordChangeSuccess,
  settingsBtn,
  settingsClose,
  settingsModal,
  settingsTabs,
  usersList,
  usersTabBtn,
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
  switchTab("cache");
  refreshCacheInfo();
  const res = await fetch("/api/cache/status");
  const status = await res.json();
  renderCacheStatus(status);
  if (status.status === "running") {
    clearTimeout(cachePollTimer);
    pollCacheStatus();
  }
  loadAccountInfo();
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

// ---------------- Tabs ----------------

const panels = { cache: panelCache, account: panelAccount, users: panelUsers };

function switchTab(name) {
  Object.entries(panels).forEach(([key, panel]) => {
    panel.hidden = key !== name;
  });
  settingsTabs.querySelectorAll(".settings-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
}

settingsTabs.addEventListener("click", (e) => {
  const btn = e.target.closest(".settings-tab");
  if (btn) switchTab(btn.dataset.tab);
});

// ---------------- Account panel ----------------

let currentUsername = null;

async function loadAccountInfo() {
  try {
    const res = await fetch("/api/account/me");
    if (!res.ok) throw new Error("me failed");
    const me = await res.json();
    currentUsername = me.username;
    accountInfoText.textContent = me.is_admin
      ? `Ingelogd als ${me.username} (beheerder).`
      : `Ingelogd als ${me.username}.`;
    usersTabBtn.hidden = !me.is_admin;
    if (me.is_admin) loadUsersList();
  } catch {
    accountInfoText.textContent = "Kon accountinformatie niet ophalen.";
  }
}

passwordChangeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  passwordChangeError.hidden = true;
  passwordChangeSuccess.hidden = true;

  if (newPasswordInput.value !== newPasswordConfirmInput.value) {
    passwordChangeError.textContent = "Nieuwe wachtwoorden komen niet overeen.";
    passwordChangeError.hidden = false;
    return;
  }

  const res = await fetch("/api/account/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPasswordInput.value,
      new_password: newPasswordInput.value,
    }),
  });
  const data = await res.json();

  if (!res.ok) {
    passwordChangeError.textContent = data.error || "Er ging iets mis.";
    passwordChangeError.hidden = false;
    return;
  }

  passwordChangeForm.reset();
  passwordChangeSuccess.hidden = false;
  showToast("Wachtwoord gewijzigd");
});

// ---------------- Users panel (admin only) ----------------

async function loadUsersList() {
  usersList.innerHTML = "Laden...";
  try {
    const res = await fetch("/api/admin/users");
    if (!res.ok) throw new Error("list failed");
    const data = await res.json();
    renderUsersList(data.users);
  } catch {
    usersList.textContent = "Kon gebruikerslijst niet ophalen.";
  }
}

function renderUsersList(users) {
  usersList.innerHTML = "";
  users.forEach((user) => {
    const row = document.createElement("div");
    row.className = "user-row";

    const name = document.createElement("span");
    name.className = "user-name";
    name.textContent = user.username;
    row.appendChild(name);

    if (user.is_admin) {
      const badge = document.createElement("span");
      badge.className = "user-badge";
      badge.textContent = "Beheerder";
      row.appendChild(badge);
    }

    const actions = document.createElement("div");
    actions.className = "user-actions";

    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.textContent = "Wachtwoord resetten";
    resetBtn.addEventListener("click", () => resetUserPassword(user.username));
    actions.appendChild(resetBtn);

    const isSelf = user.username === currentUsername;

    if (!isSelf) {
      const toggleAdminBtn = document.createElement("button");
      toggleAdminBtn.type = "button";
      toggleAdminBtn.textContent = user.is_admin ? "Beheerder intrekken" : "Beheerder maken";
      toggleAdminBtn.addEventListener("click", () => toggleUserAdmin(user.username, !user.is_admin));
      actions.appendChild(toggleAdminBtn);

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "danger";
      deleteBtn.textContent = "Verwijderen";
      deleteBtn.addEventListener("click", () => deleteUser(user.username));
      actions.appendChild(deleteBtn);
    }

    row.appendChild(actions);
    usersList.appendChild(row);
  });
}

async function resetUserPassword(username) {
  const newPassword = prompt(`Nieuw wachtwoord voor "${username}" (minstens 6 tekens):`);
  if (newPassword === null) return;
  if (newPassword.length < 6) {
    showToast("Wachtwoord moet minstens 6 tekens lang zijn.");
    return;
  }
  const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_password: newPassword }),
  });
  const data = await res.json();
  showToast(res.ok ? `Wachtwoord van ${username} gereset` : data.error || "Er ging iets mis.");
}

async function toggleUserAdmin(username, isAdmin) {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}/admin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_admin: isAdmin }),
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Er ging iets mis.");
    return;
  }
  loadUsersList();
}

async function deleteUser(username) {
  if (!confirm(`Weet je zeker dat je "${username}" wilt verwijderen? Dit kan niet ongedaan worden gemaakt.`)) {
    return;
  }
  const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Er ging iets mis.");
    return;
  }
  showToast(`${username} verwijderd`);
  loadUsersList();
}

addUserForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  addUserError.hidden = true;

  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: newUsernameInput.value.trim(),
      password: newUserPasswordInput.value,
      is_admin: newUserAdminInput.checked,
    }),
  });
  const data = await res.json();

  if (!res.ok) {
    addUserError.textContent = data.error || "Er ging iets mis.";
    addUserError.hidden = false;
    return;
  }

  addUserForm.reset();
  showToast(`Gebruiker ${data.username} toegevoegd`);
  loadUsersList();
});
