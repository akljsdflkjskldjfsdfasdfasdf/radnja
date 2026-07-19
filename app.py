# app.py — glavna datoteka aplikacije: ekrani i čuvanje podataka.

from flask import Flask, redirect, render_template, request, url_for

import baza

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


# Ovaj deo se izvršava samo kad na laptopu pokrenemo "python app.py".
# Na hostingu aplikaciju pokreće server (PythonAnywhere), pa se ovo preskače.
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
