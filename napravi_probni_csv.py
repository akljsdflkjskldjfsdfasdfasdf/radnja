# napravi_probni_csv.py — napravi izmišljeni CSV sa prodajom za poslednja 3 dana.
# Pokreni:  venv\Scripts\python napravi_probni_csv.py
# Nastane fajl prodaja_primer.csv koji onda uvezeš kroz ekran "Prodaja".

from datetime import date, timedelta
from pathlib import Path

# (barkod, naziv, prodato komada svakog dana)
ARTIKLI = [
    ("8600000000017", "Mleko 1l", 3),
    ("8600000000024", "Jogurt 500g", 1),
    ("8600000000048", "Sok od jabuke 1l", 2),
    ("8600000000055", "Kifla", 2),
    ("5555555555555", "Čips 90g", 1),   # namerno nepoznat barkod, da vidiš prijavu
]

PUTANJA = Path(__file__).parent / "prodaja_primer.csv"

redovi = ["datum;barkod;naziv;kolicina"]
danas = date.today()
for pre_dana in (3, 2, 1):
    dan = (danas - timedelta(days=pre_dana)).isoformat()
    for barkod, naziv, kolicina in ARTIKLI:
        redovi.append(f"{dan};{barkod};{naziv};{kolicina}")

PUTANJA.write_text("\n".join(redovi) + "\n", encoding="utf-8")
print(f"Napravljen {PUTANJA.name}: prodaja za 3 dana, {len(ARTIKLI)} artikala dnevno.")
