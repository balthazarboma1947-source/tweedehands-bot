import json
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import feedparser


# ============================================================
# INSTELLINGEN
# ============================================================

ZOEKOPDRACHTEN = [
    "Tap",
    "Bar",
]

MAX_PRIJS = 50

MAX_RESULTATEN = 25

SEEN_FILE = Path("seen.json")


# ============================================================
# E-MAIL INSTELLINGEN
# ============================================================

EMAIL_HOST = os.environ["EMAIL_HOST"]
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))

EMAIL_USERNAME = os.environ["EMAIL_USERNAME"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]


# ============================================================
# E-MAIL VERSTUREN
# ============================================================

def stuur_email(titel, zoekterm, prijs, link, beschrijving=""):

    bericht = EmailMessage()

    bericht["Subject"] = f"Nieuwe 2dehands-match: {titel}"
    bericht["From"] = EMAIL_FROM
    bericht["To"] = EMAIL_TO

    tekst = "🟢 NIEUWE 2DEHANDS-ADVERTENTIE\n\n"

    tekst += f"Zoekterm: {zoekterm}\n"
    tekst += f"Titel: {titel}\n"

    if prijs is not None:
        tekst += f"Prijs: €{prijs:g}\n"

    if beschrijving:

        beschrijving_schoon = re.sub(
            r"<[^>]+>",
            " ",
            beschrijving,
        )

        beschrijving_schoon = re.sub(
            r"\s+",
            " ",
            beschrijving_schoon,
        ).strip()

        if len(beschrijving_schoon) > 500:
            beschrijving_schoon = (
                beschrijving_schoon[:500] + "..."
            )

        tekst += f"\nBeschrijving:\n{beschrijving_schoon}\n"

    tekst += f"\nBekijk de advertentie:\n{link}\n"

    bericht.set_content(tekst)

    with smtplib.SMTP_SSL(
        EMAIL_HOST,
        EMAIL_PORT,
        timeout=30,
    ) as smtp:

        smtp.login(
            EMAIL_USERNAME,
            EMAIL_PASSWORD,
        )

        smtp.send_message(bericht)

    print(f"E-mail verstuurd: {titel}")


# ============================================================
# GEZIENE ADVERTENTIES
# ============================================================

def laad_gezien():

    if not SEEN_FILE.exists():
        return set()

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as bestand:

            return set(json.load(bestand))

    except Exception:

        return set()


def bewaar_gezien(gezien):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8",
    ) as bestand:

        json.dump(
            sorted(gezien),
            bestand,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# PRIJS HERKENNEN
# ============================================================

def vind_prijs(tekst):

    patronen = [
        r"€\s*([0-9][0-9\.,]*)",
        r"EUR\s*([0-9][0-9\.,]*)",
        r"([0-9][0-9\.,]*)\s*€",
        r"([0-9][0-9\.,]*)\s*EUR",
    ]

    for patroon in patronen:

        match = re.search(
            patroon,
            tekst,
            re.IGNORECASE,
        )

        if not match:
            continue

        waarde = match.group(1)

        if "," in waarde and "." in waarde:

            waarde = (
                waarde
                .replace(".", "")
                .replace(",", ".")
            )

        elif "," in waarde:

            waarde = waarde.replace(",", ".")

        elif waarde.count(".") > 1:

            waarde = waarde.replace(".", "")

        try:

            return float(waarde)

        except ValueError:

            continue

    return None


# ============================================================
# 2DEHANDS RSS
# ============================================================

def zoek_2dehands(zoekterm):

    encoded = quote(zoekterm)

    url = (
        "https://www.2dehands.be/rss/lrp/"
        f"?query={encoded}"
    )

    print(f"Zoeken: {zoekterm}")

    feed = feedparser.parse(url)

    if feed.bozo:

        print(
            "Waarschuwing bij RSS-feed:",
            feed.bozo_exception,
        )

    return feed.entries[:MAX_RESULTATEN]


# ============================================================
# ADVERTENTIE VERWERKEN
# ============================================================

def verwerk_advertentie(
    entry,
    zoekterm,
    gezien,
):

    advertentie_id = (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
    )

    if not advertentie_id:
        return False

    advertentie_id = str(advertentie_id)

    if advertentie_id in gezien:
        return False

    titel = entry.get(
        "title",
        "Zonder titel",
    )

    link = entry.get(
        "link",
        "",
    )

    samenvatting = entry.get(
        "summary",
        "",
    )

    volledige_tekst = (
        f"{titel}\n{samenvatting}"
    )

    prijs = vind_prijs(
        volledige_tekst
    )

    if (
        MAX_PRIJS is not None
        and prijs is not None
        and prijs > MAX_PRIJS
    ):

        gezien.add(
            advertentie_id
        )

        return False

    stuur_email(
        titel=titel,
        zoekterm=zoekterm,
        prijs=prijs,
        link=link,
        beschrijving=samenvatting,
    )

    gezien.add(
        advertentie_id
    )

    return True


# ============================================================
# HOOFDPROGRAMMA
# ============================================================

def main():

    print("2DEHANDS E-MAIL BOT GESTART")

    gezien = laad_gezien()

    totaal_nieuw = 0

    for zoekterm in ZOEKOPDRACHTEN:

        print(
            f"Zoeken naar: {zoekterm}"
        )

        try:

            resultaten = zoek_2dehands(
                zoekterm
            )

            print(
                f"{len(resultaten)} "
                "resultaten gevonden."
            )

            for entry in resultaten:

                try:

                    nieuw = verwerk_advertentie(
                        entry,
                        zoekterm,
                        gezien,
                    )

                    if nieuw:
                        totaal_nieuw += 1

                except Exception as fout:

                    print(
                        "Fout bij advertentie:",
                        fout,
                    )

        except Exception as fout:

            print(
                f"Fout bij zoekopdracht "
                f"'{zoekterm}': {fout}"
            )

    bewaar_gezien(gezien)

    print(
        f"Klaar. {totaal_nieuw} "
        "nieuwe advertenties."
    )


if __name__ == "__main__":
    main()
