-- schema.sql — opis svih tabela u bazi.
-- Bezbedno ga je pokrenuti više puta: "IF NOT EXISTS" znači
-- "napravi samo ako već ne postoji".

-- Radnje u lancu. V1 koristi samo jednu, ali je sve spremno za više radnji.
CREATE TABLE IF NOT EXISTS radnje (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    naziv  TEXT NOT NULL
);

-- Šifarnik proizvoda: jedan red = jedan artikal (ne pojedinačni komad).
CREATE TABLE IF NOT EXISTS proizvodi (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    barkod  TEXT UNIQUE,             -- sa ambalaže; UNIQUE = ne mogu dva ista
    naziv   TEXT NOT NULL,
    cena    REAL                     -- opciono (prazno = cena nije upisana)
);

-- Stavke prijema: jedan red = jedan prijem jednog proizvoda sa jednim rokom.
-- Isti proizvod sme da ima više redova (različiti prijemi, različiti rokovi).
CREATE TABLE IF NOT EXISTS stavke (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id       INTEGER NOT NULL REFERENCES radnje(id),
    proizvod_id    INTEGER NOT NULL REFERENCES proizvodi(id),
    rok            TEXT NOT NULL,    -- datum isteka, oblik GGGG-MM-DD
    kolicina       INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'aktivno',  -- aktivno / otpisano / snizeno
    datum_prijema  TEXT NOT NULL DEFAULT (date('now')),
    datum_promene  TEXT              -- kad je stavka označena kao otpisana/snižena
);

-- Ubrzava traženje po roku (za ekran "ističe uskoro").
CREATE INDEX IF NOT EXISTS idx_stavke_rok ON stavke(rok);
