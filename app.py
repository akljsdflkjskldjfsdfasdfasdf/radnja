# app.py — glavna datoteka aplikacije: ekrani i čuvanje podataka.

from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, url_for

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

    # Cena je opciona; prihvatamo i zapez i tačku (129,99 ili 129.99).
    cena_tekst = request.form.get("cena", "").strip().replace(",", ".")
    cena = float(cena_tekst) if cena_tekst else None

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


def _dan(broj):
    """Pravilan oblik reči: 1 dan, 2 dana, 21 dan..."""
    return "dan" if broj % 10 == 1 and broj % 100 != 11 else "dana"


@app.route("/istice")
def istice():
    """Ekran "Ističe uskoro": stavke kojima rok ističe u narednih N dana (default 3)."""
    try:
        dani = int(request.args.get("dani", 3))
    except ValueError:
        dani = 3

    danas = date.today()
    granica = (danas + timedelta(days=dani)).isoformat()

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

    return render_template("istice.html", stavke=stavke, dani=dani)


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
        SELECT s.kolicina, s.datum_promene, p.naziv, p.cena
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
