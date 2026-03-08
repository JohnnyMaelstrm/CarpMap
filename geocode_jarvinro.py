"""
geocode_jarvinro.py
-------------------
Hakee järvien koordinaatit SYKE:n järvirajapinnasta järvinumerolla.
Kentät: Nro = järvinumero, KoordErLat/KoordErLong = koordinaatit.
P�ivittää lakes_geocoded.json ja ajaa merge_data.py automaattisesti.

Aja: python3 geocode_jarvinro.py
"""

import json, requests, time, subprocess

BASE = "http://rajapinnat.ymparisto.fi/api/jarvirajapinta/1.0/odata/Jarvi"
HEADERS = {"Accept": "application/json"}

with open('lakes_geocoded.json', 'r', encoding='utf-8') as f:
    lakes = json.load(f)

print(f"Järviä yhteensä: {len(lakes)}\n")

def fetch_by_nro(nro):
    url = f"{BASE}?$filter=Nro eq '{nro}'"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            items = r.json().get('value', [])
            if items:
                return items[0]
    except Exception as e:
        print(f"  Virhe: {e}")
    return None

ok = 0
failed = []

for i, lake in enumerate(lakes):
    nro = lake.get('jarvinumero', '')
    print(f"[{i+1}/{len(lakes)}] {lake['nimi']} ({nro})...", end=' ', flush=True)

    data = fetch_by_nro(nro)
    if data:
        lat_raw = str(data.get('KoordErLat', '')).strip()
        lng_raw = str(data.get('KoordErLong', '')).strip()
        try:
            lake['lat'] = float(lat_raw)
            lake['lng'] = float(lng_raw)
            print(f"✓ {lake['lat']:.4f}, {lake['lng']:.4f}")
            ok += 1
        except ValueError:
            print(f"✗ koordinaatit puuttuvat (lat='{lat_raw}' lng='{lng_raw}')")
            failed.append(lake['nimi'])
    else:
        print(f"✗ ei löydy")
        failed.append(lake['nimi'])

    time.sleep(0.3)  # kohteliaisuustauko

# Tallenna
with open('lakes_geocoded.json', 'w', encoding='utf-8') as f:
    json.dump(lakes, f, ensure_ascii=False, indent=2)

print(f"\nValmis! {ok}/{len(lakes)} järveä koordinaateilla.")
if failed:
    print(f"Ei löydetty ({len(failed)}): {', '.join(failed)}")

# Päivitä HTML automaattisesti
print("\nPäivitetään index.html...")
subprocess.run(['python3', 'merge_data.py'])