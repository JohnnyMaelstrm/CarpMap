"""
check_protected_areas.py
"""
import json, requests, re
import geopandas as gpd
from shapely.geometry import Point

with open('lakes_geocoded.json', 'r', encoding='utf-8') as f:
    lakes = json.load(f)

lakes_with_coords = [l for l in lakes if l.get('lat') and l.get('lng')]
lats = [l['lat'] for l in lakes_with_coords]
lngs = [l['lng'] for l in lakes_with_coords]
bbox = f"{min(lngs)-0.5},{min(lats)-0.5},{max(lngs)+0.5},{max(lats)+0.5}"
print(f"Järviä koordinaateilla: {len(lakes_with_coords)}\nBbox: {bbox}\n")

BASE = "https://paikkatiedot.ymparisto.fi/geoserver"

# Selvitetään ensin mitä workspaceja on olemassa
print("=== Etsitään oikeita layer-nimiä ===")
workspaces_to_check = [
    "syke_luonnonsuojelualueet",
    "syke_ls",
    "syke",
    "SYKE_Luonnonsuojelualueet",
]
found_layers = {}
for ws in workspaces_to_check:
    url = f"{BASE}/{ws}/wfs?service=WFS&version=1.0.0&request=GetCapabilities"
    try:
        r = requests.get(url, timeout=10)
        names = re.findall(r'<(?:Name|n)>([^<]+)</(?:Name|n)>', r.text)
        names = [n for n in names if ':' in n]
        if names:
            print(f"  {ws}: {names[:6]}")
            found_layers[ws] = names
        else:
            print(f"  {ws}: ei layereita (HTTP {r.status_code})")
    except Exception as e:
        print(f"  {ws}: virhe ({e})")

# Kokeile myös yleistä WFS-listausta
print("\nKokeillaan yleistä listausta...")
try:
    r = requests.get(f"{BASE}/wfs?service=WFS&version=1.0.0&request=GetCapabilities", timeout=10)
    names = re.findall(r'<(?:Name|n)>([^<]+)</(?:Name|n)>', r.text)
    ls_names = [n for n in names if 'suojelu' in n.lower() or 'natura' in n.lower() or 'ls' in n.lower()]
    print(f"  Suojeluun liittyvät: {ls_names[:10]}")
except Exception as e:
    print(f"  Virhe: {e}")

# ---- Käytä löydettyjä layereita ----
QUERIES = []

# Lisää kaikki löydetyt suojelualue-layerit
for ws, names in found_layers.items():
    for n in names:
        if any(x in n.lower() for x in ['suojelu', 'natura', 'ls', 'protected', 'eramaa']):
            QUERIES.append({
                "name": n,
                "url": f"{BASE}/{ws}/wfs",
                "typename": n,
            })

# Lisää tiedetty erämaa-layer
QUERIES.append({
    "name": "Erämaa-alueet",
    "url": f"{BASE}/inspire_ps/wfs",
    "typename": "inspire_ps:PS.ProtectedSitesEramaaAlue",
})

# Lisää myös Metsähallituksen rajapinta jos SYKE ei toimi
QUERIES.append({
    "name": "Luonnonsuojelualueet (Metsähallitus)",
    "url": "https://julkinen.laji.fi/geoserver/wfs",
    "typename": "ktj:SuojelualuePolygon",
})

if not QUERIES:
    print("\nEi löydetty layereita automaattisesti.")
    print("Kokeillaan tunnettuja suoria URL-osoitteita...")
    QUERIES = [
        {"name": "Erämaa-alueet", "url": f"{BASE}/inspire_ps/wfs", "typename": "inspire_ps:PS.ProtectedSitesEramaaAlue"},
    ]

results = {
    lake['nimi'] + '_' + lake['region']: {
        'nimi': lake['nimi'], 'kunta': lake['kunta'],
        'region': lake['region'], 'lat': lake['lat'], 'lng': lake['lng'],
        'suojelualueet': []
    }
    for lake in lakes_with_coords
}

def fetch_and_check(q):
    print(f"\nHaetaan: {q['name']}...")
    for version in ["1.0.0", "1.1.0", "2.0.0"]:
        params = {
            'service': 'WFS', 'version': version,
            'request': 'GetFeature', 'typeName': q['typename'],
            'outputFormat': 'application/json',
            'maxFeatures': '10000', 'srsName': 'EPSG:4326',
            'bbox': bbox + (',EPSG:4326' if version != '1.0.0' else ''),
        }
        try:
            r = requests.get(q['url'], params=params, timeout=30)
            if r.status_code == 200 and 'json' in r.headers.get('content-type', ''):
                data = r.json()
                features = data.get('features', [])
                print(f"  → {len(features)} aluetta (WFS {version})")
                if not features:
                    return
                gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
                matched = 0
                for lake in lakes_with_coords:
                    point = Point(lake['lng'], lake['lat'])
                    hits = gdf[gdf.geometry.contains(point)]
                    for _, row in hits.iterrows():
                        aname = next((row.get(c) for c in ['NIMI','Nimi','nimi','NAME','name','localId'] if row.get(c)), q['name'])
                        key = lake['nimi'] + '_' + lake['region']
                        entry = f"{q['name']}: {aname}"
                        if entry not in results[key]['suojelualueet']:
                            results[key]['suojelualueet'].append(entry)
                            matched += 1
                print(f"  → {matched} osumaa järviin")
                return
        except Exception as e:
            continue
    print(f"  ✗ Kaikki versiot epäonnistuivat")

for q in QUERIES:
    fetch_and_check(q)

# ---- Tulokset ----
print("\n" + "="*60 + "\nTULOKSET\n" + "="*60)
protected = [r for r in results.values() if r['suojelualueet']]
clean = [r for r in results.values() if not r['suojelualueet']]

if protected:
    print(f"\n⚠️  SUOJELUALUEELLA ({len(protected)} järveä):\n")
    for r in protected:
        print(f"  📍 {r['nimi']} — {r['kunta']} ({r['region']})")
        for alue in r['suojelualueet']:
            print(f"     → {alue}")
else:
    print("\n✓ Yksikään järvi ei osunut suojelualueiden sisään.")

print(f"\nTarkistamatta (ei koordinaatteja): {len(lakes) - len(lakes_with_coords)} järveä")
with open('protected_areas_report.json', 'w', encoding='utf-8') as f:
    json.dump({'protected': protected, 'clean_count': len(clean),
               'total_checked': len(lakes_with_coords)}, f, ensure_ascii=False, indent=2)
print("Raportti: protected_areas_report.json")