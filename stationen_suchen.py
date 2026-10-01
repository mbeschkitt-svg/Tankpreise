#!/usr/bin/env python3
"""
Station-IDs bei Tankerkoenig finden.

Nutzung (Schluessel nur lokal setzen, nicht in Chats oder Code):
    Windows PowerShell:  $env:TANKERKOENIG_KEY = "dein-schluessel"
                         python stationen_suchen.py
    Linux/Mac:           TANKERKOENIG_KEY=dein-schluessel python3 stationen_suchen.py

Optional: Mittelpunkt und Radius anpassen:
    python stationen_suchen.py 47.98 10.18 10

Das Skript listet alle Tankstellen im Umkreis und markiert die Treffer fuer
REWE Memmingen und Eni Heimertingen mit ">>>". Die IDs sind keine Geheimnisse,
den Schluessel gibst du nie weiter.

Nur Standardbibliothek.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API_URL = "https://creativecommons.tankerkoenig.de/json/list.php"

# Standardsuche: Mitte Memmingen, 10 km (deckt Heimertingen mit ab, Limit der API: 25 km)
LAT, LNG, RADIUS = 47.98, 10.18, 10.0

# Suchmuster fuer die zwei Zieltankstellen: (Anzeigename, Strasse enthaelt, Ort enthaelt)
ZIELE = [
    ("REWE Memmingen", "rudolf", "memmingen"),
    ("Eni Heimertingen", "memminger", "heimertingen"),
]


def abrufen(lat, lng, rad, key):
    query = urllib.parse.urlencode(
        {"lat": lat, "lng": lng, "rad": rad, "type": "all", "apikey": key}
    )
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=20) as r:
        data = json.load(r)
    if not data.get("ok"):
        sys.exit(f"API-Fehler: {data.get('message', data)}")
    return data.get("stations", [])


def treffer(station):
    strasse = (station.get("street") or "").lower()
    ort = (station.get("place") or "").lower()
    for name, s, o in ZIELE:
        if s in strasse and o in ort:
            return name
    return None


def main():
    key = os.environ.get("TANKERKOENIG_KEY")
    if not key:
        sys.exit("Fehler: Umgebungsvariable TANKERKOENIG_KEY fehlt.")

    lat, lng, rad = LAT, LNG, RADIUS
    if len(sys.argv) == 4:
        lat, lng, rad = (float(x) for x in sys.argv[1:4])
    elif len(sys.argv) != 1:
        sys.exit(__doc__)

    stationen = abrufen(lat, lng, rad, key)
    if not stationen:
        sys.exit("Keine Tankstellen gefunden. Mittelpunkt und Radius pruefen.")

    gefunden = {}
    print(f"{len(stationen)} Tankstellen im Umkreis von {rad:g} km\n")
    for s in sorted(stationen, key=lambda x: x.get("dist", 0)):
        ziel = treffer(s)
        marke = ">>>" if ziel else "   "
        adresse = f"{s.get('street', '')} {s.get('houseNumber', '')}".strip()
        print(f"{marke} {s['id']}  {s.get('brand') or s.get('name')}, "
              f"{adresse}, {s.get('postCode', '')} {s.get('place', '')}")
        if ziel:
            gefunden.setdefault(ziel, []).append(s["id"])

    print("\nErgebnis fuer deine Tankstellen:")
    for name, _, _ in ZIELE:
        ids = gefunden.get(name, [])
        if len(ids) == 1:
            print(f"  {name}: {ids[0]}")
        elif not ids:
            print(f"  {name}: nicht gefunden. Suche in der Liste oben selbst nach der Adresse.")
        else:
            print(f"  {name}: mehrere Treffer {ids}. Adresse in der Liste oben pruefen.")


if __name__ == "__main__":
    main()
