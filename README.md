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
