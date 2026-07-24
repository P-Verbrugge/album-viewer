# Album Viewer

A self-hosted, lightweight album viewer that runs on your own folder
structure — no Immich or other photo-management software required. Works
like Synology Photos:

- The home screen shows your top-level folders as albums (with a cover photo).
- Does an album contain subfolders? Then you see those subfolders (again as tiles).
- No more subfolders, but photos? Then you see the photos themselves, and can
  click one for a full-size view with arrow-key navigation.

## Quick start

1. In `docker-compose.yml`, change the path `/path/to/your/photos` to the
   folder on your host system that contains your photos.
2. Start the container:

   ```bash
   docker compose up -d --build
   ```

3. Open `http://<your-server>:8080` in your browser.

## Configuration

Via environment variables (see `docker-compose.yml`):

| Variable      | Meaning                                        | Default   |
|---------------|-------------------------------------------------|-----------|
| `PHOTOS_ROOT` | Folder inside the container with your photos     | `/photos` |
| `CACHE_DIR`   | Folder where thumbnails/app data are cached      | `/cache`  |
| `THUMB_SIZE`  | Default thumbnail width in pixels                 | `400`     |

Photos are mounted **read-only** (`:ro`), so the app can never modify or
delete anything on your disk.

## How a folder is displayed

For every folder, in this order:

1. **Does the folder contain subfolders?** Show those subfolders as album
   tiles (each with a cover photo: the first photo found, searched up to 3
   levels deep).
2. **No subfolders, but photos?** Show the photos themselves, as a grid.
3. **Both empty?** Show an empty state.

Note: if a folder contains both subfolders *and* loose photos directly, this
logic only shows the subfolders (the loose photos in that folder stay
hidden, unless you move them into a subfolder). Let me know if you'd rather
have both shown at once — that's a small change.

## Settings

The ⚙ icon (top right) shows how many photos already have a thumbnail and
how much space the cache takes up. **"Cache nu volledig aanmaken"** ("Build
full cache now") processes every photo in the library in one go (with a
progress bar), so you never have to wait while browsing. **"Cache legen"**
("Clear cache") removes all generated thumbnails again (e.g. if you want a
clean start after a lot of changes to your photo folder) — your favorites
are kept regardless.

## Features

- **Light/dark theme**: button top right (◐). Preference is remembered in
  your browser. The photo viewer itself always stays dark — that's
  intentional, so the photo stays the focus without a bright background
  competing for attention.
- **Favorites**: click the heart on a photo tile or in the viewer. Favorites
  are personal to your account (stored server-side in
  `CACHE_DIR/favorites.json`, so they persist in the `album-viewer-cache`
  volume) — nobody else sees what you've favorited. Click the heart icon top
  right in the toolbar for an overview of your favorites.
- **EXIF info**: click the ⓘ icon in the photo viewer for camera, lens,
  shutter speed, aperture, ISO, focal length, and date taken (as far as
  present in the file). If the photo has a GPS location, a small map (via
  OpenStreetMap) appears too. Note: for the map, the viewer's browser needs
  internet access (map tiles come from openstreetmap.org) — the server
  itself doesn't need anything extra.
- **Map overview**: the ⌖ button in the toolbar opens a map with all photos
  that have a GPS location (clustered together when zoomed out, so it stays
  readable with lots of photos). Click a pin (or a cluster to zoom in), then
  click a photo in the popup to open it directly in the viewer.

  A photo only gets a spot on the map once it has been viewed or cached —
  the location data is built up at the same moment a thumbnail is
  generated (no separate, slow scan of your whole library needed). If you
  haven't viewed many photos yet, use "Cache nu volledig aanmaken" in
  Settings to process everything at once — after that the map will be
  complete right away.

  Popup thumbnails load on demand, one at a time, only once you actually
  open that pin's popup — not all at once when the map opens. With a lot of
  geotagged photos, loading every thumbnail up front would hammer the
  server with requests and often show blank/broken images while they're
  still competing to load.

## Login & user accounts

The app is protected by user accounts — nobody can see the albums without
logging in. Multiple people can each have their own account.

- **First time opening**: you'll see a "Create account" screen. The account
  you create here automatically becomes the **admin**.
- **Admin**: open Instellingen (⚙) — it's a full-screen panel with a sidebar
  menu (Cache / Account / Gebruikers). See who's logged in and change your
  own password on the **Account** tab. Admins get an extra **Gebruikers**
  tab to:
  - add new accounts (optionally as another admin),
  - reset anyone's password,
  - promote/demote admins,
  - delete an account.

  Any admin can manage any other user. There must always be at least one
  admin — the app blocks removing the last one, and you can never delete or
  demote your own account (to avoid accidentally locking yourself out).
- **Regular (non-admin) accounts** can change their own password (Account
  tab) but don't see the Gebruikers tab.
- **Favorites are personal**: each account has its own favorites list —
  nobody sees anyone else's.
- **Passwords** are stored locally, always hashed (never in plain text), in
  `CACHE_DIR/users.json` — so in the `album-viewer-cache` volume, and this
  survives a container restart.
- **Locked out entirely** (e.g. forgot the only admin's password and there's
  no other admin to reset it)? Delete the whole user store to start over
  with a fresh "Create account" screen:
  ```bash
  docker exec -it album-viewer rm -f /cache/users.json
  ```
  This removes all accounts (not your photos or favorites), and the first
  person to open the app afterwards becomes the new admin.
- **Upgrading from an older version** (single shared account): your existing
  login is automatically migrated into the new system as the first admin
  account the first time the app starts — no action needed, no re-setup.

### Why gunicorn runs with `--preload`

The Dockerfile starts gunicorn with `--preload`. This matters specifically
for the very first startup on a brand-new, empty cache volume: the app
generates a random session-signing key and saves it to
`CACHE_DIR/secret_key.txt` the first time it's needed. Without `--preload`,
each of gunicorn's worker processes would generate that key independently
(a race), so a login cookie signed by one worker wouldn't be recognized by
the other — causing random, seemingly unpredictable "sometimes logged in,
sometimes not" behavior depending on which worker handled a given request.
With `--preload`, the app (and that key) is created once, before gunicorn
forks its workers, so every worker shares the exact same key. This was
verified directly against real gunicorn with multiple worker processes.

## Video clips

Short video clips (`.mp4 .mov .m4v .avi .webm`) show up right alongside your
photos — same grid, same albums, same favorites and downloads. A small ▶
badge on the tile tells them apart from photos.

- **Thumbnails**: generated with `ffmpeg` (a still frame ~1 second in,
  falling back to the very first frame for very short clips), cached the
  same way as photo thumbnails.
- **Viewer**: clicking a video opens it with normal playback controls
  (play/pause/volume/seek) — nothing autoplays outside of slideshow mode.
- **Slideshow mode**: videos advance on the *same fixed interval* as photos
  rather than playing to completion — they autoplay muted as a moving
  preview for their slot, then the slideshow just moves on. Let me know if
  you'd rather have it wait for full playback instead; that's a reasonable
  follow-up change.
- **EXIF/map**: videos don't get EXIF info or a spot on the map overview
  (that's photo-specific metadata) — the info panel just shows the filename
  for a video.
- Running without Docker? Make sure `ffmpeg` is installed on your system
  (`apt install ffmpeg` / `brew install ffmpeg`) — the Docker image already
  includes it.

## Downloading

- **A single photo**: the ⬇ button in the viewer downloads the **original
  file** — never the display-converted JPEG used for HEIC previews, so you
  always get full quality and metadata.
- **A whole album as a zip**: the "⬇ Album downloaden" button (next to the
  slideshow button) zips every photo in the current view. On an album that
  has sub-albums (e.g. "Italy" with year folders inside), this grabs
  **everything recursively**, keeping the folder structure inside the zip.
- **Favorites as a zip**: the same button appears on the Favorites overview
  and zips all your favorited photos, regardless of which folders they're
  actually in.

Zips are generated on the fly and cleaned up right after sending — nothing
lingers on disk. Very large selections (over 3000 photos in one go) are
rejected with a clear message asking you to download a smaller (sub)folder
instead, to keep the server responsive.

## Slideshow mode

Every photo grid (an album's photos, or your Favorites) shows a "▶ Start
slideshow" button. Click it to open the viewer and automatically advance
through the photos — it loops back to the start once it reaches the end.

- **Interval**: pick 3s / 5s / 8s / 15s / 30s from the dropdown in the
  viewer's toolbar. Your choice is remembered for next time.
- **Fullscreen**: the ⛶ button makes the viewer take up the whole screen —
  handy when showing photos on a TV.
- **Auto-hiding controls**: while playing, the buttons and counter fade out
  after a few seconds of no activity (like a video player), and reappear as
  soon as you move the mouse or tap the screen.
- You can still navigate manually with the arrow keys or by clicking
  prev/next while a slideshow is running — it just continues counting down
  from wherever you land. Space bar toggles play/pause.

## Performance with large folders

Folders with a huge number of photos or subfolders directly inside them
(hundreds to thousands) are no longer loaded all at once. The server sends
them in pages of 300 items, and the app automatically loads the next page
as you scroll toward the bottom of the screen ("infinite scroll") — you
normally won't notice this at all, except that browsing large albums stays
smooth instead of building thousands of tiles at once.

## Building from GitHub (no more manual file copying)

You can have Docker fetch the code directly from GitHub when building,
instead of manually copying files to your TrueNAS server.

1. Put the project folder in your own GitHub repository (see `.gitignore`).
2. In `docker-compose.yml`, switch the `build:` section to Option B (see the
   comment lines in that file) and fill in your own GitHub URL.
3. On TrueNAS you then only need `docker-compose.yml` — put that one file in
   e.g. `/mnt/YourPool/apps/photo-album-app/` and run:

   ```bash
   docker compose up -d --build
   ```

   Docker clones the repo internally (via BuildKit) and builds the image —
   you never need to run `git clone` yourself.

### Updating after a code change

```bash
git add . && git commit -m "change" && git push     # on your own PC
```
And then on TrueNAS:
```bash
docker compose up -d --build
```
Docker fetches the latest commit on the `main` branch on every build — a
`git pull` on TrueNAS itself is not needed.

**Two things to keep in mind:**
- **Private repository**: this only works with a **public** repo as set up
  here. For a private repo you'd need an SSH context or a token in the URL
  (`https://<token>@github.com/...`), which isn't ideal to put in a compose
  file. For a personal hobby project without sensitive data, a public repo
  is generally fine.
- **Build cache**: if a build oddly seems to use your old code, force a
  fresh clone with:
  ```bash
  docker compose build --no-cache && docker compose up -d
  ```

## Supported formats

Photos: `.jpg .jpeg .png .gif .webp .bmp .tiff .heic .heif`
Videos: `.mp4 .mov .m4v .avi .webm`

HEIC/HEIF (the format iPhones use) is supported via the `pillow-heif`
package in `requirements.txt`. Thumbnails and the full-size view are both
automatically converted to JPEG, since no mainstream browser besides Safari
can display HEIC directly.

## Project structure

```
photo-album-app/
├── app.py                 # thin entry point (creates the app via album_app.create_app())
├── album_app/
│   ├── __init__.py        # application factory: wires up sessions + all blueprints
│   ├── config.py          # env vars, paths, file-type constants
│   ├── exif_utils.py      # pure EXIF-parsing helpers
│   ├── media.py           # path safety, file-type checks, thumbnails, GPS index
│   ├── auth.py            # multi-user store, /setup, /login, /logout, login guard
│   ├── account_routes.py  # /api/account/me, /api/account/password (self-service)
│   ├── admin_users.py     # /api/admin/users/* (admin-only user management)
│   ├── pages.py           # "/" — the single-page-app shell
│   ├── browse.py          # /api/browse — folders/photos + pagination
│   ├── media_routes.py    # /api/thumbnail, /api/image, /api/video
│   ├── favorites.py       # /api/favorites/toggle (per-account favorites)
│   ├── exif_routes.py     # /api/exif
│   ├── gps_map.py         # /api/map/photos
│   ├── downloads.py       # /api/download/photo, /api/download/zip
│   └── cache_job.py       # bulk-cache background job + /api/cache/*
├── templates/              # index.html, login.html, setup.html
└── static/
    ├── style.css
    └── js/                 # ES modules — see static/js/main.js for the module map
```

## Running without Docker (local testing)

```bash
pip install -r requirements.txt
PHOTOS_ROOT=/path/to/photos CACHE_DIR=/tmp/album-cache python app.py
```

The app is then reachable at `http://localhost:8080`.
