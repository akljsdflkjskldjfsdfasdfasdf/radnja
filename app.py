# app.py — glavna datoteka aplikacije: ekrani i čuvanje podataka.

import sqlite3
from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, send_file, url_for

import baza
import uvoz_prodaje

app = Flask(__name__)

# Pri pokretanju se uverimo da baza i tabele postoje.
baza.pripremi_bazu()


def trenutna_radnja(veza):
    """V1 radi sa jednom radnjom — uzmi njen id (spremno za više radnji kasnije)."""
    return veza.execute("SELECT id FROM radnje LIMIT 1").fetchone()["id"]


@app.route("/")
def prijem():
    """Početni ekran: unos barkoda (kamerom ili ručno)."""
    return render_template("prijem.html")


@app.route("/prijem", methods=["POST"])
def prijem_barkod():
    """Stigao barkod — proveri da li proizvod postoji u šifarniku."""
    barkod = request.form["barkod"].strip()
    veza = baza.konekcija()
    proizvod = veza.execute(
        "SELECT * FROM proizvodi WHERE barkod = ?", (barkod,)
    ).fetchone()
    veza.close()

    if proizvod is None:
        return render_template("novi.html", barkod=barkod)
    return render_template("poznat.html", proizvod=proizvod)


@app.route("/prijem/sacuvaj", methods=["POST"])
def prijem_sacuvaj():
    """Poznat proizvod: upiši stavku prijema (rok + količina)."""
    proizvod_id = int(request.form["proizvod_id"])
    rok = request.form["rok"]
    kolicina = int(request.form["kolicina"])

    veza = baza.konekcija()
    veza.execute(
        "INSERT INTO stavke (store_id, proizvod_id, rok, kolicina) VALUES (?, ?, ?, ?)",
        (trenutna_radnja(veza), proizvod_id, rok, kolicina),
    )
    veza.commit()
    naziv = veza.execute(
        "SELECT naziv FROM proizvodi WHERE id = ?", (proizvod_id,)
    ).fetchone()["naziv"]
    veza.close()

    return redirect(url_for("prijem", poruka=f"✔ {naziv}: {kolicina} kom, rok {rok}"))


@app.route("/prijem/sacuvaj-novi", methods=["POST"])
def prijem_sacuvaj_novi():
    """Nepoznat proizvod: dodaj ga u šifarnik pa odmah upiši i prijem."""
    barkod = request.form["barkod"].strip()
    naziv = request.form["naziv"].strip()
    rok = request.form["rok"]
    kolicina = int(request.form["kolicina"])

    cena = _u_cenu(request.form.get("cena"))

    veza = baza.konekcija()
    # "OR IGNORE": ako je neko u međuvremenu već dodao ovaj barkod, ne pravi duplikat.
    veza.execute(
        "INSERT OR IGNORE INTO proizvodi (barkod, naziv, cena) VALUES (?, ?, ?)",
        (barkod, naziv, cena),
    )
    proizvod_id = veza.execute(
        "SELECT id FROM proizvodi WHERE barkod = ?", (barkod,)
    ).fetchone()["id"]
    veza.execute(
        "INSERT INTO stavke (store_id, proizvod_id, rok, kolicina) VALUES (?, ?, ?, ?)",
        (trenutna_radnja(veza), proizvod_id, rok, kolicina),
    )
    veza.commit()
    veza.close()

    return redirect(url_for("prijem", poruka=f"✔ Nov proizvod {naziv}: {kolicina} kom, rok {rok}"))


def _u_cenu(tekst):
    """Cena je opciona; prihvatamo i zapetu i tačku (129,99 ili 129.99)."""
    tekst = (tekst or "").strip().replace(",", ".")
    return float(tekst) if tekst else None


def _dan(broj):
    """Pravilan oblik reči: 1 dan, 2 dana, 21 dan..."""
    return "dan" if broj % 10 == 1 and broj % 100 != 11 else "dana"


@app.route("/istice")
def istice():
    """Ekran "Ističe uskoro": filter 3/7/30 dana ili "sve" (svaka aktivna stavka)."""
    izbor = request.args.get("dani", "3")
    danas = date.today()
    if izbor == "sve":
        granica = "9999-12-31"      # praktično: bez ograničenja
    else:
        try:
            granica = (danas + timedelta(days=int(izbor))).isoformat()
        except ValueError:
            izbor = "3"
            granica = (danas + timedelta(days=3)).isoformat()

    veza = baza.konekcija()
    redovi = veza.execute(
        """
        SELECT s.id, s.rok, s.kolicina, s.status, p.naziv
        FROM stavke s
        JOIN proizvodi p ON p.id = s.proizvod_id
        WHERE s.status != 'otpisano' AND s.rok <= ?
        ORDER BY s.rok
        """,
        (granica,),
    ).fetchall()
    veza.close()

    # Za svaku stavku spremimo čitljivu oznaku ("ističe sutra") i boju hitnosti.
    stavke = []
    for red in redovi:
        razlika = (date.fromisoformat(red["rok"]) - danas).days
        if razlika < -1:
            oznaka, boja = f"isteklo pre {-razlika} {_dan(-razlika)}", "isteklo"
        elif razlika == -1:
            oznaka, boja = "isteklo juče", "isteklo"
        elif razlika == 0:
            oznaka, boja = "ističe DANAS", "hitno"
        elif razlika == 1:
            oznaka, boja = "ističe sutra", "hitno"
        else:
            oznaka, boja = f"ističe za {razlika} {_dan(razlika)}", "ok"
        stavke.append(dict(red) | {"oznaka": oznaka, "boja": boja})

    return render_template("istice.html", stavke=stavke, izbor=izbor)


@app.route("/stavka/<int:stavka_id>/status", methods=["POST"])
def promeni_status(stavka_id):
    """Dugmad na stavci: označi kao "otpisano" (sklonjeno) ili "snizeno"."""
    novi_status = request.form["status"]
    if novi_status not in ("otpisano", "snizeno"):
        return redirect(url_for("istice"))

    veza = baza.konekcija()
    stavka = veza.execute(
        "SELECT p.naziv FROM stavke s JOIN proizvodi p ON p.id = s.proizvod_id WHERE s.id = ?",
        (stavka_id,),
    ).fetchone()
    if stavka is None:
        veza.close()
        return redirect(url_for("istice"))

    veza.execute(
        "UPDATE stavke SET status = ?, datum_promene = date('now') WHERE id = ?",
        (novi_status, stavka_id),
    )
    veza.commit()
    veza.close()

    tekst = "sklonjena/otpisana" if novi_status == "otpisano" else "označena kao snižena"
    return redirect(url_for(
        "istice",
        dani=request.form.get("dani", 3),
        poruka=f"✔ {stavka['naziv']}: {tekst}",
    ))


def _lep_broj(broj, decimala=1):
    """9.0 prikaži kao "9", a 1.2857 kao "1,3" (srpska zapeta)."""
    if broj == int(broj):
        return str(int(broj))
    return f"{broj:.{decimala}f}".replace(".", ",")


@app.route("/prodaja")
def prodaja_statistika():
    """Top artikli: šta se najviše prodaje i kojom brzinom (komada dnevno)."""
    try:
        dani = int(request.args.get("dani", 7))
    except ValueError:
        dani = 7

    # Period: poslednjih N dana, računajući i danas.
    od = (date.today() - timedelta(days=dani - 1)).isoformat()

    veza = baza.konekcija()
    redovi = veza.execute(
        """
        SELECT p.naziv, SUM(pr.kolicina) AS ukupno
        FROM prodaja pr
        JOIN proizvodi p ON p.id = pr.proizvod_id
        WHERE pr.datum >= ?
        GROUP BY pr.proizvod_id
        ORDER BY ukupno DESC
        """,
        (od,),
    ).fetchall()
    veza.close()

    artikli = [{
        "naziv": red["naziv"],
        "ukupno": _lep_broj(red["ukupno"]),
        # Brzina prodaje: prosek po danu — ova brojka će u Fazi 3
        # određivati kada je vreme za poručivanje.
        "brzina": _lep_broj(red["ukupno"] / dani),
    } for red in redovi]

    return render_template("prodaja.html", artikli=artikli, dani=dani)


@app.route("/stavka/<int:stavka_id>/izmena")
def stavka_izmena(stavka_id):
    """Ekran za ispravku pogrešno unetog roka ili količine."""
    veza = baza.konekcija()
    stavka = veza.execute(
        "SELECT s.id, s.rok, s.kolicina, s.datum_prijema, p.naziv "
        "FROM stavke s JOIN proizvodi p ON p.id = s.proizvod_id WHERE s.id = ?",
        (stavka_id,),
    ).fetchone()
    veza.close()
    if stavka is None:
        return redirect(url_for("istice"))
    return render_template("izmena.html", stavka=stavka)


@app.route("/stavka/<int:stavka_id>/izmena", methods=["POST"])
def stavka_izmena_sacuvaj(stavka_id):
    veza = baza.konekcija()
    veza.execute(
        "UPDATE stavke SET rok = ?, kolicina = ? WHERE id = ?",
        (request.form["rok"], int(request.form["kolicina"]), stavka_id),
    )
    veza.commit()
    veza.close()
    return redirect(url_for("istice", dani="sve", poruka="✔ Unos izmenjen"))


@app.route("/stavka/<int:stavka_id>/obrisi", methods=["POST"])
def stavka_obrisi(stavka_id):
    """Brisanje je za greške u kucanju — sklonjena roba ide u otpis, ne ovde."""
    veza = baza.konekcija()
    veza.execute("DELETE FROM stavke WHERE id = ?", (stavka_id,))
    veza.commit()
    veza.close()
    return redirect(url_for("istice", dani="sve", poruka="✔ Unos obrisan"))


@app.route("/stavka/<int:stavka_id>/vrati", methods=["POST"])
def stavka_vrati(stavka_id):
    """Poništi otpis (slučajan klik) — stavka se vraća u "aktivno"."""
    veza = baza.konekcija()
    veza.execute(
        "UPDATE stavke SET status = 'aktivno', datum_promene = NULL WHERE id = ?",
        (stavka_id,),
    )
    veza.commit()
    veza.close()
    return redirect(url_for("otpis", poruka="✔ Otpis poništen — stavka je vraćena"))


@app.route("/proizvodi")
def proizvodi():
    """Šifarnik artikala: pregled i ulaz za izmenu naziva/cene."""
    veza = baza.konekcija()
    redovi = veza.execute(
        "SELECT id, barkod, naziv, cena FROM proizvodi ORDER BY naziv"
    ).fetchall()
    veza.close()
    lista = [{
        "id": red["id"],
        "barkod": red["barkod"],
        "naziv": red["naziv"],
        "cena_tekst": _dinari(red["cena"]) if red["cena"] is not None else "—",
    } for red in redovi]
    return render_template("proizvodi.html", proizvodi=lista)


@app.route("/proizvod/<int:proizvod_id>/izmena")
def proizvod_izmena(proizvod_id):
    veza = baza.konekcija()
    proizvod = veza.execute(
        "SELECT id, barkod, naziv, cena FROM proizvodi WHERE id = ?", (proizvod_id,)
    ).fetchone()
    veza.close()
    if proizvod is None:
        return redirect(url_for("proizvodi"))
    return render_template("proizvod_izmena.html", proizvod=proizvod)


@app.route("/proizvod/<int:proizvod_id>/izmena", methods=["POST"])
def proizvod_izmena_sacuvaj(proizvod_id):
    veza = baza.konekcija()
    veza.execute(
        "UPDATE proizvodi SET naziv = ?, cena = ? WHERE id = ?",
        (request.form["naziv"].strip(), _u_cenu(request.form.get("cena")), proizvod_id),
    )
    veza.commit()
    veza.close()
    return redirect(url_for("proizvodi", poruka="✔ Artikal izmenjen"))


@app.route("/backup")
def backup():
    """Preuzmi kopiju cele baze — jedan fajl, čuvaj ga s vremena na vreme."""
    izvor = baza.konekcija()
    putanja_kopije = baza.PUTANJA_BAZE.with_name("kopija-baze.db")
    kopija = sqlite3.connect(putanja_kopije)
    izvor.backup(kopija)                 # sigurno kopiranje i dok aplikacija radi
    kopija.close()
    izvor.close()
    return send_file(putanja_kopije, as_attachment=True,
                     download_name=f"radnja-{date.today().isoformat()}.db")


@app.route("/zalihe")
def zalihe():
    """Stanje zaliha po artiklu: primljeno − prodato − otpisano."""
    veza = baza.konekcija()
    sid = trenutna_radnja(veza)

    def zbirovi(upit, parametri):
        """Vrati rečnik: proizvod_id -> zbir količina."""
        return {red["proizvod_id"]: red["ukupno"]
                for red in veza.execute(upit, parametri).fetchall()}

    prijemi = zbirovi(
        "SELECT proizvod_id, SUM(kolicina) AS ukupno FROM stavke "
        "WHERE store_id = ? GROUP BY proizvod_id", (sid,))
    otpisi = zbirovi(
        "SELECT proizvod_id, SUM(kolicina) AS ukupno FROM stavke "
        "WHERE store_id = ? AND status = 'otpisano' GROUP BY proizvod_id", (sid,))
    prodaje = zbirovi(
        "SELECT proizvod_id, SUM(kolicina) AS ukupno FROM prodaja "
        "WHERE store_id = ? GROUP BY proizvod_id", (sid,))
    nazivi = {red["id"]: red["naziv"]
              for red in veza.execute("SELECT id, naziv FROM proizvodi").fetchall()}
    veza.close()

    redovi = []
    for pid, naziv in nazivi.items():
        prijem = prijemi.get(pid, 0)
        otpis = otpisi.get(pid, 0)
        prodato = prodaje.get(pid, 0)
        if prijem == 0 and otpis == 0 and prodato == 0:
            continue                      # artikal bez ikakvog prometa ne gura se u tabelu
        stanje = prijem - prodato - otpis
        redovi.append({
            "naziv": naziv,
            "prijem": _lep_broj(prijem),
            "prodato": _lep_broj(prodato),
            "otpis": _lep_broj(otpis),
            "stanje": _lep_broj(stanje),
            "minus": stanje < 0,
        })

    # Najmanje stanje na vrh — to je ono što treba prvo videti.
    redovi.sort(key=lambda red: float(str(red["stanje"]).replace(",", ".")))
    ima_minusa = any(red["minus"] for red in redovi)

    return render_template("zalihe.html", redovi=redovi, ima_minusa=ima_minusa)


@app.route("/prodaja/uvoz")
def uvoz_ekran():
    """Ekran za uvoz prodaje iz CSV fajla."""
    return render_template("uvoz.html", rezultat=None)


@app.route("/prodaja/uvoz", methods=["POST"])
def uvoz_obrada():
    """Stigao fajl — pročitaj ga i prikaži izveštaj šta je uvezeno."""
    fajl = request.files.get("fajl")
    if fajl is None or fajl.filename == "":
        return render_template("uvoz.html", rezultat={
            "ok": False, "poruka_greske": "Nisi izabrao fajl.",
        })

    veza = baza.konekcija()
    rezultat = uvoz_prodaje.uvezi_csv(fajl.read(), trenutna_radnja(veza), veza)
    veza.close()
    return render_template("uvoz.html", rezultat=rezultat)


MESECI = {
    "01": "januar", "02": "februar", "03": "mart", "04": "april",
    "05": "maj", "06": "jun", "07": "jul", "08": "avgust",
    "09": "septembar", "10": "oktobar", "11": "novembar", "12": "decembar",
}


def _mesec_naziv(kljuc):
    """Od "2026-07" napravi "jul 2026"."""
    godina, mesec = kljuc.split("-")
    return f"{MESECI[mesec]} {godina}"


def _dinari(iznos):
    """Broj u tekst sa zapetom: 959.94 -> "959,94"."""
    return f"{iznos:.2f}".replace(".", ",")


@app.route("/otpis")
def otpis():
    """Mesečni zbir otpisa: koliko je stavki sklonjeno i koliko to vredi."""
    veza = baza.konekcija()
    redovi = veza.execute(
        """
        SELECT s.id, s.kolicina, s.datum_promene, p.naziv, p.cena
        FROM stavke s
        JOIN proizvodi p ON p.id = s.proizvod_id
        WHERE s.status = 'otpisano' AND s.datum_promene IS NOT NULL
        ORDER BY s.datum_promene DESC
        """
    ).fetchall()
    veza.close()

    # Grupišemo po mesecu ("2026-07"), od najnovijeg ka starijem.
    meseci = {}
    for red in redovi:
        kljuc = red["datum_promene"][:7]
        grupa = meseci.setdefault(kljuc, {
            "naziv": _mesec_naziv(kljuc),
            "stavki": 0, "komada": 0, "vrednost": 0.0, "bez_cene": 0,
            "lista": [],
        })
        grupa["stavki"] += 1
        grupa["komada"] += red["kolicina"]
        if red["cena"] is None:
            grupa["bez_cene"] += 1          # bez cene ne možemo u vrednost
        else:
            grupa["vrednost"] += red["kolicina"] * red["cena"]
        grupa["lista"].append(red)

    for grupa in meseci.values():
        grupa["vrednost_tekst"] = _dinari(grupa["vrednost"])

    return render_template("otpis.html", meseci=meseci)


# Ovaj deo se izvršava samo kad na laptopu pokrenemo "python app.py".
# Na hostingu aplikaciju pokreće server (PythonAnywhere), pa se ovo preskače.
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
