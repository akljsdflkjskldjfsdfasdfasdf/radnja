# uvoz_prodaje.py — čitanje CSV fajla sa prodajom i upis u bazu.
# CSV mora imati zaglavlje sa kolonama: datum, barkod, kolicina (naziv nije obavezan).
# Trudimo se da progutamo razne varijante: ";" ili "," između kolona,
# datume "2026-07-18" i "18.07.2026", količine "3" i "2,5", stara Windows slova.

import csv
import io
from datetime import datetime

# Dozvoljena imena kolona u fajlu -> naše ime.
IMENA_KOLONA = {
    "datum": "datum", "dan": "datum",
    "barkod": "barkod", "ean": "barkod", "bar-kod": "barkod", "bar kod": "barkod",
    "naziv": "naziv", "artikal": "naziv", "proizvod": "naziv",
    "kolicina": "kolicina", "količina": "kolicina", "kom": "kolicina", "qty": "kolicina",
}

FORMATI_DATUMA = ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%Y.")


def _u_tekst(sadrzaj_bajtova):
    """Pretvori bajtove fajla u tekst (novi programi: UTF-8; stari: Windows-1250)."""
    try:
        return sadrzaj_bajtova.decode("utf-8-sig")
    except UnicodeDecodeError:
        return sadrzaj_bajtova.decode("cp1250")


def _u_datum(tekst):
    """Prihvati "2026-07-18" ili "18.07.2026" -> uvek vrati "2026-07-18"."""
    for oblik in FORMATI_DATUMA:
        try:
            return datetime.strptime(tekst.strip(), oblik).date().isoformat()
        except ValueError:
            pass
    return None


def _lepa_kolicina(broj):
    """3.0 prikaži kao 3, a 2.5 ostavi kao 2.5."""
    return int(broj) if broj == int(broj) else broj


def uvezi_csv(sadrzaj_bajtova, store_id, veza):
    """Pročitaj CSV i upiši prodaju. Vraća izveštaj o svemu što se desilo."""
    tekst = _u_tekst(sadrzaj_bajtova)
    linije = tekst.splitlines()
    if not linije:
        return {"ok": False, "poruka_greske": "Fajl je prazan."}

    # Srpski Excel često koristi ";" umesto "," — pogodi po prvom redu.
    razdvajac = ";" if linije[0].count(";") >= linije[0].count(",") else ","

    citac = csv.DictReader(io.StringIO(tekst), delimiter=razdvajac)

    # Prevedi imena kolona iz fajla u naša (npr. "Količina" -> "kolicina").
    kolone = {}
    for ime in citac.fieldnames or []:
        nase = IMENA_KOLONA.get((ime or "").strip().lower())
        if nase and nase not in kolone:
            kolone[nase] = ime
    nedostaju = [k for k in ("datum", "barkod", "kolicina") if k not in kolone]
    if nedostaju:
        return {"ok": False, "poruka_greske": (
            f"U fajlu ne postoje kolone: {', '.join(nedostaju)}. "
            f"Nađeno u fajlu: {', '.join(citac.fieldnames or [])}."
        )}

    # Saberi po (barkod, dan) — ako fajl ima više redova za isti artikal, spoji ih.
    zbir = {}
    nazivi = {}
    greske = []
    for broj_reda, red in enumerate(citac, start=2):   # red 1 je zaglavlje
        barkod = (red[kolone["barkod"]] or "").strip()
        if not barkod:
            continue                                    # prazan red preskačemo ćutke
        datum = _u_datum(red[kolone["datum"]] or "")
        if datum is None:
            greske.append(f"red {broj_reda}: ne razumem datum '{red[kolone['datum']]}'")
            continue
        try:
            kolicina = float((red[kolone["kolicina"]] or "").strip().replace(",", "."))
        except ValueError:
            greske.append(f"red {broj_reda}: ne razumem količinu '{red[kolone['kolicina']]}'")
            continue
        zbir[(barkod, datum)] = zbir.get((barkod, datum), 0) + kolicina
        if "naziv" in kolone and red[kolone["naziv"]]:
            nazivi[barkod] = red[kolone["naziv"]].strip()

    # Upis u bazu: poznate artikle upiši (isti dan = zameni), nepoznate prijavi.
    uvezeno = 0
    dani = set()
    nepoznati = {}
    for (barkod, datum), kolicina in zbir.items():
        proizvod = veza.execute(
            "SELECT id FROM proizvodi WHERE barkod = ?", (barkod,)
        ).fetchone()
        if proizvod is None:
            n = nepoznati.setdefault(barkod, {"naziv": nazivi.get(barkod, ""), "kolicina": 0})
            n["kolicina"] += kolicina
            continue
        veza.execute(
            """
            INSERT INTO prodaja (store_id, proizvod_id, datum, kolicina)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(store_id, proizvod_id, datum)
            DO UPDATE SET kolicina = excluded.kolicina
            """,
            (store_id, proizvod["id"], datum, kolicina),
        )
        uvezeno += 1
        dani.add(datum)
    veza.commit()

    return {
        "ok": True,
        "uvezeno": uvezeno,
        "dani": sorted(dani),
        "nepoznati": [
            {"barkod": b, "naziv": p["naziv"], "kolicina": _lepa_kolicina(p["kolicina"])}
            for b, p in nepoznati.items()
        ],
        "greske": greske,
    }
