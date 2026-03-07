"""
merge_data.py
-------------
Lukee lakes_geocoded.json ja päivittää karppi-kartta.html.
Aja geocode_lakes.py ensin, sitten tämä.
"""

import json, re

with open('lakes_geocoded.json', 'r', encoding='utf-8') as f:
    all_lakes = json.load(f)

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

new_data = 'const LAKES_DATA = ' + json.dumps(all_lakes, ensure_ascii=False) + ';'
html = re.sub(r'const LAKES_DATA = \[.*?\];', new_data, html, flags=re.DOTALL)

# Update lake/stocking counts in header
located = sum(1 for l in all_lakes if l.get('lat'))
total_stockings = sum(len(l['istutukset']) for l in all_lakes)
html = re.sub(r'(<span class="stat-val" id="stat-jarvet">)\d+(</span>)', 
              rf'\g<1>{len(all_lakes)}\g<2>', html)
html = re.sub(r'(<span class="stat-val" id="stat-istutukset">)\d+(</span>)', 
              rf'\g<1>{total_stockings}\g<2>', html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Updated! {len(all_lakes)} lakes ({located} with coordinates), {total_stockings} stocking events.")
