# Album Viewer

Een eigen, lichte albumviewer die op je eigen mapstructuur draait — geen Immich
of andere fotobeheer-software nodig. Werkt zoals Synology Photos:

- Startscherm toont je hoofdmappen als albums (met een omslagfoto).
- Zitten er submappen in een album? Dan zie je die submappen (weer als tegels).
- Zitten er geen submappen meer in, maar wel foto's? Dan zie je de foto's,
  en kun je erop klikken voor een volledige weergave met pijltjestoetsen-navigatie.

## Snel starten

1. Pas in `docker-compose.yml` het pad `/pad/naar/jouw/fotos` aan naar de map
   op je host-systeem met je foto's.
2. Start de container:

   ```bash
   docker compose up -d --build
   ```

3. Open `http://<jouw-server>:8080` in je browser.

## Configuratie

Via omgevingsvariabelen (zie `docker-compose.yml`):

| Variabele     | Betekenis                                    | Default   |
|---------------|-----------------------------------------------|-----------|
| `PHOTOS_ROOT` | Map in de container met je foto's             | `/photos` |
| `CACHE_DIR`   | Map waar thumbnails gecached worden           | `/cache`  |
| `THUMB_SIZE`  | Standaard thumbnail-breedte in pixels          | `400`     |

De foto's worden **read-only** gemount (`:ro`), dus de app kan nooit iets op je
schijf wijzigen of verwijderen.

## Hoe een map wordt getoond

Voor elke map geldt, in deze volgorde:

1. **Bevat de map submappen?** Toon die submappen als album-tegels (elk met
   een omslagfoto: de eerste gevonden foto, tot 3 niveaus diep gezocht).
2. **Geen submappen, maar wel foto's?** Toon de foto's zelf, als grid.
3. **Beide leeg?** Toon een lege staat.

Let op: als een map zowel submappen áls losse foto's direct bevat, worden
volgens deze logica alleen de submappen getoond (de losse foto's in die map
blijven dan onzichtbaar, tenzij je ze in een submap zet). Laat het weten als
je liever hebt dat beide tegelijk getoond worden — dat is een kleine aanpassing.

- **Instellingen** (⚙-icoon rechtsboven): laat zien hoeveel foto's al een
  thumbnail hebben en hoeveel ruimte de cache inneemt. Met **"Cache nu
  volledig aanmaken"** worden alle foto's in de bibliotheek in één keer
  verwerkt (met een voortgangsbalk), zodat je nooit meer hoeft te wachten
  tijdens het bladeren. Met **"Cache legen"** verwijder je alle gegenereerde
  thumbnails weer (bijv. als je opnieuw wilt beginnen na veel wijzigingen in
  je fotomap) — je favorieten blijven daarbij gewoon bewaard.

## Nieuwe features

- **Licht/donker thema**: knop rechtsboven (◐). Voorkeur wordt onthouden in je
  browser. De foto-viewer zelf blijft altijd donker, dat is bewust — zo blijft
  de foto het middelpunt zonder afleiding van een felle achtergrond.
- **Favorieten**: klik op het hartje op een foto-tegel of in de viewer. Favorieten
  worden server-side opgeslagen (in `CACHE_DIR/favorites.json`, dus bewaard in
  het `album-viewer-cache` volume) en zijn dus voor iedereen zichtbaar die de
  app bezoekt. Klik op het hartje-icoon rechtsboven in de topbalk voor een
  overzicht van al je favorieten.
- **EXIF-informatie**: klik op het ⓘ-icoon in de foto-viewer voor camera, lens,
  sluitertijd, diafragma, ISO, brandpuntsafstand en opnamedatum (voor zover
  aanwezig in het bestand). Staat er GPS-locatie in de foto, dan verschijnt er
  ook een kaartje (via OpenStreetMap). Let op: voor het kaartje moet de browser
  van de kijker internettoegang hebben (de kaarttegels komen van
  openstreetmap.org) — de server zelf hoeft niets extra's te doen.

## Bouwen vanaf GitHub (geen handmatige bestandskopieën meer)

Je kunt Docker de code rechtstreeks van GitHub laten ophalen bij het bouwen,
in plaats van bestanden handmatig naar je TrueNAS-server te kopiëren.

1. Zet de projectmap in een eigen GitHub-repository (zie `.gitignore`).
2. Zet in `docker-compose.yml` de `build:`-sectie op Optie B (zie de
   commentaarregels in dat bestand) en vul je eigen GitHub-URL in.
3. Op TrueNAS heb je dan alleen nog `docker-compose.yml` nodig — plaats dat
   ene bestand in bijv. `/mnt/JePool/apps/photo-album-app/` en run:

   ```bash
   docker compose up -d --build
   ```

   Docker kloont de repo intern (via BuildKit) en bouwt de image — je hoeft
   zelf nooit `git clone` te draaien.

### Updaten na een codewijziging

```bash
git add . && git commit -m "wijziging" && git push     # op je eigen PC
```
En dan op TrueNAS:
```bash
docker compose up -d --build
```
Docker haalt bij elke build de laatste commit van de `main`-branch op — een
`git pull` op TrueNAS zelf is dus niet nodig.

**Let op — twee dingen om te weten:**
- **Privé-repository**: dit werkt zo alleen bij een **publieke** repo. Voor
  een privé-repo moet je een SSH-context of een token in de URL meegeven
  (`https://<token>@github.com/...`), wat minder wenselijk is om in een
  compose-bestand te zetten. Voor persoonlijke hobbyprojecten zonder
  gevoelige data is een publieke repo doorgaans prima.
- **Build-cache**: als een build merkwaardig genoeg je oude code lijkt te
  gebruiken, forceer een verse clone met:
  ```bash
  docker compose build --no-cache && docker compose up -d
  ```

## Inloggen

De app is nu afgeschermd met een gebruikersaccount — niemand kan de albums
zien zonder in te loggen.

- **Eerste keer openen**: je krijgt een "Account aanmaken"-scherm te zien.
  Kies daar zelf een gebruikersnaam en wachtwoord (minimaal 6 tekens). Dit
  wordt lokaal opgeslagen (het wachtwoord altijd gehasht, nooit in platte
  tekst) in `CACHE_DIR/account.json` — dus in het `album-viewer-cache`
  volume, en overleeft dus een herstart van de container.
- **Daarna**: iedereen die de app bezoekt krijgt een inlogscherm en heeft dit
  ene account nodig.
- **Wachtwoord vergeten / opnieuw beginnen**: verwijder het bestand
  `account.json` uit de cache, dan verschijnt het "Account aanmaken"-scherm
  weer:
  ```bash
  docker exec -it album-viewer rm -f /cache/account.json
  ```
- Er is momenteel maar **één account** ondersteund (geen aparte
  gebruikersnamen per gezinslid) — iedereen die toegang moet hebben, deelt
  dezelfde inloggegevens. Laat het weten als je losse accounts per persoon
  wilt, dat is goed uit te breiden.

## Ondersteunde formaten

`.jpg .jpeg .png .gif .webp .bmp .tiff .heic`

(HEIC-bestanden worden gedetecteerd, maar Pillow kan ze zonder extra plugin
niet altijd openen — laat het weten als je veel iPhone-foto's in HEIC hebt,
dan voeg ik `pillow-heif` toe.)

## Zonder Docker draaien (lokaal testen)

```bash
pip install -r requirements.txt
PHOTOS_ROOT=/pad/naar/fotos CACHE_DIR=/tmp/album-cache python app.py
```

Dan is de app bereikbaar op `http://localhost:8080`.
