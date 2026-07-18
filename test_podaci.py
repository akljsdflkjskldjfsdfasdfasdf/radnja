# test_podaci.py — ubaci izmišljene test podatke i ispiši šta je u bazi.
# Pokreće se ručno iz terminala:  venv\Scripts\python test_podaci.py
# Slobodno ga pokreći više puta — stare test stavke obriše, pa ubaci sveže.

from datetime import date, timedelta

import baza

# Izmišljeni proizvodi: (barkod, naziv, cena) — None znači "cena nije upisana".
PROIZVODI = [
    ("8600000000017", "Mleko 1l", 129.99),
    ("8600000000024", "Jogurt 500g", 89.99),
    ("8600000000031", "Kačkavalj 300g", 459.00),
    ("8600000000048", "Sok od jabuke 1l", None),
    ("8600000000055", "Kifla", 45.00),
]

# Stavke prijema: (barkod, za koliko dana ističe, količina).
# Negativan broj = već istekao, da vidimo i taj slučaj.
STAVKE = [
    ("8600000000055", -1, 4),   # kifle istekle juče
    ("8600000000017", 1, 6),    # mleko ističe sutra
    ("8600000000024", 2, 3),
    ("8600000000017", 5, 12),   # isti proizvod, drugi prijem, kasniji rok
    ("8600000000048", 10, 8),
    ("8600000000031", 30, 2),
]


def ubaci_test_podatke():
    baza.pripremi_bazu()
    veza = baza.konekcija()

    store_id = veza.execute("SELECT id FROM radnje LIMIT 1").fetchone()["id"]

    # "OR IGNORE": ako barkod već postoji, preskoči — nema duplikata.
    for barkod, naziv, cena in PROIZVODI:
        veza.execute(
            "INSERT OR IGNORE INTO proizvodi (barkod, naziv, cena) VALUES (?, ?, ?)",
            (barkod, naziv, cena),
        )

    # Test stavke uvek ispočetka, da rokovi budu "oko današnjeg dana".
    veza.execute("DELETE FROM stavke")
    danas = date.today()
    for barkod, za_dana, kolicina in STAVKE:
        proizvod = veza.execute(
            "SELECT id FROM proizvodi WHERE barkod = ?", (barkod,)
        ).fetchone()
        rok = (danas + timedelta(days=za_dana)).isoformat()
        veza.execute(
            "INSERT INTO stavke (store_id, proizvod_id, rok, kolicina) VALUES (?, ?, ?, ?)",
            (store_id, proizvod["id"], rok, kolicina),
        )

    veza.commit()

    # Ispiši sadržaj baze sortiran po roku — klica budućeg ekrana "ističe uskoro".
    redovi = veza.execute(
        """
        SELECT p.naziv, s.rok, s.kolicina, s.status
        FROM stavke s
        JOIN proizvodi p ON p.id = s.proizvod_id
        ORDER BY s.rok
        """
    ).fetchall()
    veza.close()

    print(f"\nU bazi: {len(redovi)} stavki (sortirano po roku)\n")
    print(f"{'PROIZVOD':<20} {'ROK':<12} {'KOM':>4}  STATUS")
    print("-" * 46)
    for red in redovi:
        print(f"{red['naziv']:<20} {red['rok']:<12} {red['kolicina']:>4}  {red['status']}")
    print()


if __name__ == "__main__":
    ubaci_test_podatke()
