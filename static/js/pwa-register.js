// Registers the service worker for PWA installability. This silently does
// nothing if the browser doesn't support it, or if we're not in a "secure
// context" (plain HTTP on anything other than localhost) — no error shown
// to the user either way, the app just works without it in that case.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {
      // Expected on plain HTTP LAN addresses — service workers require a
      // secure context. Nothing to do here.
    });
  });
}
