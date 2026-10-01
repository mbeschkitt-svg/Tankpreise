#!/usr/bin/env python3
"""
Tankpreise: E10-Preise zweier Tankstellen erfassen und nach 8 Wochen auswerten.

Nutzung:
    python tankpreise.py collect   # einmal Preise abrufen und in tankpreise.csv speichern
    python tankpreise.py analyze   # Auswertung nach Uhrzeit, Wochentag und Standort

Einrichtung:
    1. Kostenlosen API-Schluessel bei Tankerkoenig holen (creativecommons.tankerkoenig.de).
    2. Station-IDs (UUIDs) beider Tankstellen in STATIONS eintragen.
    3. Schluessel als Umgebungsvariable TANKERKOENIG_KEY setzen.
    4. collect alle 10 Minuten automatisch starten (Windows Aufgabenplanung oder cron).

Nur Standardbibliothek, keine zusaetzlichen Pakete noetig.
"""
import csv
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from statistics import mean
from zoneinfo import ZoneInfo

# IDs kommen aus Umgebungsvariablen (in GitHub als Repository-Variablen hinterlegt)
STATIONS = {
    "REWE Memmingen": os.environ.get("STATION_REWE", "HIER-UUID-EINTRAGEN"),
    "Eni Heimertingen": os.environ.get("STATION_ENI", "HIER-UUID-EINTRAGEN"),
}
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tankpreise.csv")
API_URL = "https://creativecommons.tankerkoenig.de/json/prices.php"
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def collect():
    key = os.environ.get("TANKERKOENIG_KEY")
    if not key:
        sys.exit("Fehler: Umgebungsvariable TANKERKOENIG_KEY fehlt.")
    if any(v.startswith("HIER") for v in STATIONS.values()):
        sys.exit("Fehler: Station-IDs in STATIONS eintragen.")

    ids = ",".join(STATIONS.values())
    with urllib.request.urlopen(f"{API_URL}?ids={ids}&apikey={key}", timeout=20) as r:
        data = json.load(r)
    if not data.get("ok"):
        sys.exit(f"API-Fehler: {data.get('message', data)}")

    # Immer deutsche Ortszeit speichern, auch wenn der Server in UTC läuft
    now = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
    new_file = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["zeit", "station", "status", "e10"])
        for name, sid in STATIONS.items():
            p = data["prices"].get(sid, {})
            e10 = p.get("e10")
            w.writerow([now, name, p.get("status", "unbekannt"), e10 if e10 else ""])


def lade():
    rows = []
    with open(CSV_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["e10"]:
                rows.append((datetime.strptime(r["zeit"], "%Y-%m-%d %H:%M:%S"),
                             r["station"], float(r["e10"])))
    return rows


def analyze():
    rows = lade()
    if not rows:
        sys.exit("Keine Daten in tankpreise.csv.")
    tage = {r[0].date() for r in rows}
    print(f"Datenbasis: {len(rows)} Messwerte an {len(tage)} Tagen "
          f"({min(tage)} bis {max(tage)})\n")

    # Tagesmittel je Station, damit Ölpreis-Trends den Uhrzeiteffekt nicht verfälschen
    tagesmittel = defaultdict(list)
    for t, s, p in rows:
        tagesmittel[(s, t.date())].append(p)
    tagesmittel = {k: mean(v) for k, v in tagesmittel.items()}

    # 1. Abweichung vom Tagesmittel je Stunde (Cent)
    print("Uhrzeit: Abweichung vom Tagesmittel in Cent (negativ = günstiger)")
    je_stunde = defaultdict(lambda: defaultdict(list))
    for t, s, p in rows:
        je_stunde[s][t.hour].append((p - tagesmittel[(s, t.date())]) * 100)
    for s, h in je_stunde.items():
        print(f"\n  {s}")
        for stunde in sorted(h):
            print(f"    {stunde:02d} Uhr: {mean(h[stunde]):+.1f}")
        guenstigste = min(h, key=lambda x: mean(h[x]))
        print(f"    Günstigste Stunde: {guenstigste:02d} Uhr")

    # 2. Wochentag: Tagesmittel gegen Wochenmittel (gleiche ISO-Woche)
    print("\nWochentag: Abweichung vom Wochenmittel in Cent (nur volle Wochen sinnvoll)")
    wochen = defaultdict(list)
    for (s, tag), m in tagesmittel.items():
        wochen[(s, tag.isocalendar()[:2])].append(m)
    wochenmittel = {k: mean(v) for k, v in wochen.items()}
    je_tag = defaultdict(lambda: defaultdict(list))
    for (s, tag), m in tagesmittel.items():
        je_tag[s][tag.weekday()].append((m - wochenmittel[(s, tag.isocalendar()[:2])]) * 100)
    for s, d in je_tag.items():
        werte = ", ".join(f"{WOCHENTAGE[i]} {mean(d[i]):+.1f}" for i in sorted(d))
        print(f"  {s}: {werte}")

    # 3. Standortvergleich zum selben Zeitpunkt
    print("\nStandortvergleich (gleiche Messzeit, Cent Unterschied)")
    je_zeit = defaultdict(dict)
    for t, s, p in rows:
        je_zeit[t][s] = p
    namen = list(STATIONS)
    diffs = [(v[namen[0]] - v[namen[1]]) * 100 for v in je_zeit.values()
             if namen[0] in v and namen[1] in v]
    if diffs:
        print(f"  {namen[0]} minus {namen[1]}: {mean(diffs):+.1f} Cent im Mittel "
              f"({len(diffs)} Vergleichspunkte)")
        print(f"  {namen[0]} war in {sum(d < 0 for d in diffs) / len(diffs):.0%} "
              f"der Messungen günstiger.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("collect", "analyze"):
        sys.exit(__doc__)
    collect() if sys.argv[1] == "collect" else analyze()
