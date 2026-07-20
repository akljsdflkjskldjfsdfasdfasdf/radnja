# demo_podaci.py — napuni bazu bogatim, realističnim IZMIŠLJENIM podacima.
# Namena: da imaš čime da se igraš i da pokažeš aplikaciju u radnji.
#
# PAŽNJA: ovo BRIŠE sve postojeće proizvode, prijeme, prodaju i otpise
# i ubacuje sveže demo podatke. Radnja (naziv) ostaje.
# Pokretanje:  python demo_podaci.py   (na serveru: unutar ~/radnja)
#
# Svi podaci su izmišljeni. Nazivi proizvoda su uobičajeni tržišni artikli
# radi realnosti; nijedan pravi podatak firme se ne koristi.

import random
from datetime import date, timedelta

import baza

random.seed(42)   # isti "slučajni" podaci svaki put — da demo bude predvidiv

# (barkod, naziv, cena u dinarima, prosečna dnevna prodaja u komadima)
PROIZVODI = [
    ("8600100000011", "Mleko 2.8% 1l", 129.99, 9),
    ("8600100000028", "Jogurt čaša 180g", 49.99, 12),
    ("8600100000035", "Kiseli jogurt 500g", 89.99, 5),
    ("8600100000042", "Pavlaka 20% 400g", 159.99, 3),
    ("8600100000059", "Sir feta 200g", 219.00, 2),
    ("8600100000066", "Kačkavalj 300g", 459.00, 2),
    ("8600100000073", "Maslac 250g", 289.00, 2),
    ("8600100000080", "Jaja 10 kom", 249.00, 6),
    ("8600200000010", "Hleb beli 500g", 69.99, 22),
    ("8600200000027", "Hleb crni 500g", 89.99, 8),
    ("8600200000034", "Kifla", 45.00, 30),
    ("8600200000041", "Burek sa sirom", 159.00, 14),
    ("8600300000019", "Pašteta 100g", 79.99, 7),
    ("8600300000026", "Viršle 500g", 329.00, 4),
    ("8600300000033", "Salama pileća 100g", 119.00, 5),
    ("8600300000040", "Slanina dimljena 200g", 349.00, 2),
    ("8600400000018", "Coca-Cola 2l", 219.00, 10),
    ("8600400000025", "Sok narandža 1l", 149.00, 6),
    ("8600400000032", "Voda negazirana 1.5l", 69.99, 15),
    ("8600400000049", "Voda gazirana 1.5l", 69.99, 8),
    ("8600400000056", "Pivo 0.5l", 109.00, 11),
    ("8600400000063", "Energetsko piće 250ml", 189.00, 5),
    ("8600500000017", "Čips 90g", 149.00, 9),
    ("8600500000024", "Smoki 50g", 69.99, 13),
    ("8600500000031", "Čokolada mlečna 80g", 139.00, 7),
    ("8600500000048", "Napolitanke 50g", 59.99, 10),
    ("8600500000055", "Keks 150g", 99.00, 6),
    ("8600500000062", "Bombone 100g", 129.00, 4),
    ("8600600000016", "Kafa mlevena 200g", 349.00, 3),
    ("8600600000023", "Čaj kamilica 20 kesica", 149.00, 2),
    ("8600600000030", "Šećer 1kg", 119.00, 4),
    ("8600600000047", "Brašno T-400 1kg", 89.99, 3),
    ("8600600000054", "Ulje suncokret 1l", 199.00, 5),
    ("8600700000015", "Deterdžent za sudove 500ml", 179.00, 2),
    ("8600700000022", "Toalet papir 10 rolni", 299.00, 3),
    ("8600700000039", "Sapun 100g", 79.99, 3),
]

# Kako se rokovi trajanja ponašaju po grupama (radi realnosti):
# sveže (mleko, hleb, pekara) imaju kratke rokove, ostalo duže.
KRATAK_ROK = {"Mleko", "Jogurt", "Pavlaka", "Hleb", "Kifla", "Burek", "Sir", "Pašteta"}


def kratak(naziv):
    return any(naziv.startswith(k) for k in KRATAK_ROK)


def napuni():
    veza = baza.konekcija()
    danas = date.today()

    # 1. Obriši stare podatke (radnju zadržavamo)
    veza.execute("DELETE FROM prodaja")
    veza.execute("DELETE FROM stavke")
    veza.execute("DELETE FROM proizvodi")
    store_id = veza.execute("SELECT id FROM radnje LIMIT 1").fetchone()["id"]

    # 2. Proizvodi
    id_po_barkodu = {}
    for barkod, naziv, cena, _ in PROIZVODI:
        cur = veza.execute(
            "INSERT INTO proizvodi (barkod, naziv, cena) VALUES (?, ?, ?)",
            (barkod, naziv, cena),
        )
        id_po_barkodu[barkod] = cur.lastrowid

    # 3. Prijemi (stavke) — svaki proizvod ima 1–2 prijema sa raznim rokovima
    broj_prijema = 0
    for barkod, naziv, cena, dnevno in PROIZVODI:
        pid = id_po_barkodu[barkod]
        if kratak(naziv):
            # sveža roba: rok od -2 do +4 dana (neki već istekli — da "Ističe" ima šta da pokaže)
            rokovi = [random.randint(-2, 4)]
        else:
            # trajna roba: jedan bliži i jedan dalji rok
            rokovi = [random.randint(3, 20), random.randint(60, 300)]
        for pomak in rokovi:
            rok = (danas + timedelta(days=pomak)).isoformat()
            kolicina = random.randint(8, 40)
            veza.execute(
                "INSERT INTO stavke (store_id, proizvod_id, rok, kolicina, datum_prijema) "
                "VALUES (?, ?, ?, ?, ?)",
                (store_id, pid, rok, kolicina,
                 (danas - timedelta(days=random.randint(1, 20))).isoformat()),
            )
            broj_prijema += 1

    # 4. Prodaja — poslednjih 30 dana, dnevna količina oko proseka artikla
    broj_prodaja = 0
    for barkod, naziv, cena, dnevno in PROIZVODI:
        pid = id_po_barkodu[barkod]
        for pre in range(1, 31):
            dan = (danas - timedelta(days=pre)).isoformat()
            # vikendom se prodaje više, ponekad 0 (nije bilo prodaje tog dana)
            kolicina = max(0, int(random.gauss(dnevno, dnevno * 0.4)))
            if kolicina == 0:
                continue
            veza.execute(
                "INSERT INTO prodaja (store_id, proizvod_id, datum, kolicina) VALUES (?, ?, ?, ?)",
                (store_id, pid, dan, kolicina),
            )
            broj_prodaja += 1

    # 5. Otpisi — istorija otpisane robe kroz prošlih 45 dana (ovaj i prošli mesec),
    # da izveštaj "Otpis" ima šta da pokaže. Otpisujemo uglavnom kvarljivu robu.
    kvarljivi = [b for b, naziv, *_ in PROIZVODI if kratak(naziv)]
    broj_otpisa = 0
    for _ in range(16):
        barkod = random.choice(kvarljivi)
        pid = id_po_barkodu[barkod]
        pre_dana = random.randint(0, 12) if broj_otpisa % 2 == 0 else random.randint(32, 45)
        datum_otpisa = danas - timedelta(days=pre_dana)
        # Otpisana stavka: primljena par dana ranije, rok istekao na dan otpisa.
        veza.execute(
            "INSERT INTO stavke (store_id, proizvod_id, rok, kolicina, status, "
            "datum_prijema, datum_promene) VALUES (?, ?, ?, ?, 'otpisano', ?, ?)",
            (store_id, pid, datum_otpisa.isoformat(), random.randint(1, 5),
             (datum_otpisa - timedelta(days=random.randint(2, 5))).isoformat(),
             datum_otpisa.isoformat()),
        )
        broj_otpisa += 1

    veza.commit()
    veza.close()

    print("Demo podaci ubačeni:")
    print(f"  proizvoda: {len(PROIZVODI)}")
    print(f"  prijema:   {broj_prijema}")
    print(f"  prodaja:   {broj_prodaja} (poslednjih 30 dana)")
    print(f"  otpisa:    {broj_otpisa}")


if __name__ == "__main__":
    napuni()
