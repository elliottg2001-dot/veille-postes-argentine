#!/usr/bin/env python3
"""
veille.py — Agent de veille CDI/Stage/VIE Argentine
Entreprises françaises · GitHub Actions · toutes les 10 min
"""

import json
import os
import re
import sys
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
STATE_FILE  = BASE_DIR / "state.json"

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")
BOT_NAME    = "Agent Argentine 🤖"

COULEUR_SUCCES  = 3066993   # Vert
COULEUR_INFO    = 3447003   # Bleu
COULEUR_ALERTE  = 15844367  # Orange
COULEUR_ERREUR  = 15158332  # Rouge

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
ARGENTINA_KEYWORDS = [
    "argentina", "argentine", "buenos aires", "córdoba", "cordoba",
    "rosario", "mendoza", "pilar", "tucumán", "tucuman", "mar del plata",
    "la plata", "salta", "santa fe", "martínez", "martinez", "tigre",
    "san isidro", "hurlingham", "zárate", "zarate", "campana", "luján", "lujan",
]

EXCLUDED_COUNTRIES = [
    "france", "india", "inde", "espagne", "spain", "brasil", "brazil",
    "chile", "chili", "colombia", "peru", "pérou", "mexico", "mexique",
    "usa", "états-unis", "etats-unis", "united states", "germany", "allemagne",
]

EXCLUDED_PATTERNS = [
    "banco de talentos", "talent pool", "pool de talentos",
    "brandstorm", "hackathon", "competition", "concurso",
    "cvthèque", "base de cv",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,fr;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SECTEURS = {
    "TotalEnergies": "Énergie",
    "Carrefour Argentina": "Distribution",
    "Schneider Electric": "Industrie / Énergie",
    "Danone Argentina": "Agroalimentaire",
    "Capgemini": "Conseil / Tech",
    "Air Liquide": "Industrie / Chimie",
    "CMA CGM": "Transport / Logistique",
    "ID Logistics": "Logistique",
    "Coface": "Finance / Assurance",
    "Veolia": "Environnement",
    "Renault Argentina": "Automobile",
    "Stellantis": "Automobile",
    "Sanofi Argentina": "Santé / Pharma",
    "L'Oréal Argentina": "Cosmétiques / FMCG",
    "Saint-Gobain": "Industrie / BTP",
    "Alstom": "Transport / Industrie",
    "BNP Paribas": "Finance / Banque",
    "Pernod Ricard": "Agroalimentaire",
    "Vallourec": "Industrie / Métallurgie",
    "OPmobility": "Automobile",
    "Louis Dreyfus Company": "Agroalimentaire",
    "AXA Partners": "Finance / Assurance",
    "Accor": "Hôtellerie / Tourisme",
}

LINKEDIN_SLUGS = {
    "TotalEnergies": "totalenergies",
    "Carrefour Argentina": "carrefour",
    "Schneider Electric": "schneider-electric",
    "Danone Argentina": "danone",
    "Capgemini": "capgemini",
    "Air Liquide": "air-liquide",
    "CMA CGM": "cma-cgm",
    "ID Logistics": "id-logistics",
    "Coface": "coface",
    "Veolia": "veolia",
    "Renault Argentina": "renault",
    "Stellantis": "stellantis",
    "Sanofi Argentina": "sanofi",
    "L'Oréal Argentina": "loreal",
    "Saint-Gobain": "saint-gobain",
    "Alstom": "alstomgroup",
    "BNP Paribas": "bnp-paribas",
    "Pernod Ricard": "pernod-ricard",
    "Vallourec": "vallourec",
    "OPmobility": "opmobility",
    "Louis Dreyfus Company": "louis-dreyfus-company",
    "AXA Partners": "axa-partners",
    "Accor": "accor",
}


# ─── DISCORD ──────────────────────────────────────────────────────────────────

TYPE_BADGE = {
    "VIE":                     "🌍 VIE",
    "Stage":                   "🎓 Stage",
    "CDD":                     "📆 CDD",
    "CDI":                     "💼 CDI",
    "Programme Jeune Diplômé": "⭐ Jeune Diplômé",
}

TYPE_COULEUR = {
    "VIE":                     3447003,
    "Stage":                   15844367,
    "CDD":                     10181046,
    "CDI":                     3066993,
    "Programme Jeune Diplômé": 16776960,
}

TYPE_ORDRE = ["VIE", "Stage", "CDD", "CDI", "Programme Jeune Diplômé"]

SECTEUR_EMOJI = {
    "Conseil / Tech":          "💻",
    "Santé / Pharma":          "💊",
    "Cosmétiques / FMCG":      "💄",
    "Énergie":                 "⚡",
    "Industrie / Énergie":     "⚡",
    "Agroalimentaire":         "🌾",
    "Finance / Assurance":     "🏦",
    "Finance / Banque":        "🏦",
    "Transport / Logistique":  "🚢",
    "Logistique":              "📦",
    "Automobile":              "🚗",
    "Environnement":           "🌿",
    "Industrie / Chimie":      "🧪",
    "Industrie / BTP":         "🏗️",
    "Transport / Industrie":   "🚄",
    "Industrie / Métallurgie": "⚙️",
    "Hôtellerie / Tourisme":   "🏨",
    "Distribution":            "🛒",
}


def discord_send(payload: dict) -> bool:
    if not WEBHOOK_URL:
        print("  ⚠️  DISCORD_WEBHOOK non défini")
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            WEBHOOK_URL,
            data    = data,
            headers = {"Content-Type": "application/json", "User-Agent": "Agent-Argentine/1.0"},
            method  = "POST",
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [Discord] Erreur : {e}")
        return False


def discord_offres(offres: list) -> bool:
    if not offres:
        return discord_rien_de_nouveau()

    groupes = {}
    for o in offres:
        t = o.get("type", "CDI")
        groupes.setdefault(t, []).append(o)

    summary_parts = []
    for t in TYPE_ORDRE:
        if t in groupes:
            n = len(groupes[t])
            badge = TYPE_BADGE.get(t, t)
            summary_parts.append(f"{badge} ×{n}" if n > 1 else badge)
    for t, lst in groupes.items():
        if t not in TYPE_ORDRE:
            badge = TYPE_BADGE.get(t, f"📄 {t}")
            summary_parts.append(f"{badge} ×{len(lst)}" if len(lst) > 1 else badge)

    recap_embed = {
        "title":       f"🚨  {len(offres)} nouvelle(s) offre(s) en Argentine  🇦🇷",
        "description": (
            f"**{len(offres)} opportunité(s)** correspondent à tes critères !\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{'  ·  '.join(summary_parts)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "color": COULEUR_SUCCES,
        "footer": {
            "text": f"🤖 Agent Argentine  ·  Vérifié le {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}"
        },
    }

    type_embeds = []
    ordre_final = [t for t in TYPE_ORDRE if t in groupes]
    ordre_final += [t for t in groupes if t not in TYPE_ORDRE]

    for type_c in ordre_final:
        lst    = groupes[type_c]
        badge  = TYPE_BADGE.get(type_c, f"📄 {type_c}")
        color  = TYPE_COULEUR.get(type_c, COULEUR_INFO)
        fields = []
        for o in lst[:8]:
            sect_em = SECTEUR_EMOJI.get(o.get("secteur", ""), "🏢")
            lines = [
                f"{sect_em}  **{o.get('entreprise', '?')}**",
                f"📍  {o.get('lieu', '?')}",
                f"🏷️  {TYPE_BADGE.get(o.get('type','CDI'), o.get('type','CDI'))}",
            ]
            if o.get("date"):
                lines.append(f"📅  Détecté le {o['date']}")
            if o.get("lien"):
                lines.append(f"\n🔗  {o['lien']}")
            fields.append({"name": f"┌─  {o.get('titre','?')}", "value": "\n".join(lines), "inline": False})
            if o != lst[min(7, len(lst)-1)]:
                fields.append({"name": "\u200b", "value": "\u200b", "inline": False})

        type_embeds.append({"title": f"{badge}  —  {len(lst)} offre(s)", "color": color, "fields": fields})

    return discord_send({
        "username": BOT_NAME,
        "embeds":   [recap_embed] + type_embeds[:9],
    })


def discord_rien_de_nouveau() -> bool:
    return discord_send({
        "username": BOT_NAME,
        "embeds": [{
            "title":       "🔍  Vérification terminée — rien de nouveau",
            "description": (
                "Aucune nouvelle offre détectée via Argentine — Toutes sources.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅  Toutes les sources ont été consultées\n"
                "📂  L'état de référence est à jour"
            ),
            "color":  COULEUR_INFO,
            "footer": {"text": f"🤖 Agent Argentine  ·  {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}"},
        }]
    })


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace"), None
    except urllib.error.HTTPError as e:
        return "", f"HTTP {e.code} — {url}"
    except urllib.error.URLError as e:
        return "", f"URLError — {e.reason}"
    except Exception as e:
        return "", f"Erreur — {e}"


def is_argentina(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ARGENTINA_KEYWORDS)


def is_excluded_country(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in EXCLUDED_COUNTRIES)


def is_excluded_offer(titre: str) -> bool:
    t = titre.lower()
    return any(kw in t for kw in EXCLUDED_PATTERNS)


def qualify_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["vie", "v.i.e.", "volontariat international"]):
        return "VIE"
    if any(k in t for k in ["pasant", "pasantía", "intern", "internship", "stage", "practicante"]):
        return "Stage"
    if any(k in t for k in ["cdd", "temporaire", "eventual", "contrato a plazo", "temporario"]):
        return "CDD"
    if any(k in t for k in ["trainee", "graduate", "joven profesional", "young professional"]):
        return "Programme Jeune Diplômé"
    return "CDI"


def build_uid(entreprise: str, titre: str, lieu: str) -> str:
    return f"{entreprise.strip().lower()}|{titre.strip().lower()}|{lieu.strip().lower()}"


# ─── STATE ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_offers": [], "last_run": ""}


def save_state(state: dict, new_jobs: list):
    for job in new_jobs:
        uid = build_uid(job["entreprise"], job["titre"], job["lieu"])
        if uid not in state["known_offers"]:
            state["known_offers"].append(uid)
    state["last_run"] = datetime.datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"✅ State — {len(state['known_offers'])} offres connues")


# ─── SOURCE A : BUSINESS FRANCE (VIE) ────────────────────────────────────────

def scrape_business_france() -> list:
    print("\n📡 SOURCE A — Business France (VIE)...")
    url = "https://mon-vie-via.businessfrance.fr/offres/recherche?query=Argentine"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  {err}")
        return []

    offers = []
    blocks = re.findall(
        r'<(?:article|div|li)[^>]*class="[^"]*(?:card|item|offre|mission|result)[^"]*"[^>]*>(.*?)</(?:article|div|li)>',
        html, re.DOTALL | re.IGNORECASE
    )

    processed = set()
    for block in blocks:
        title_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', block, re.IGNORECASE)
        if not title_m:
            title_m = re.search(r'(?:title|aria-label)="([^"]+)"', block, re.IGNORECASE)
        if not title_m:
            continue
        titre = title_m.group(1).strip()
        if is_excluded_offer(titre):
            continue
        if not is_argentina(block):
            continue
        loc_m = re.search(
            r'(?:Buenos Aires|Pilar|Córdoba|Cordoba|Mendoza|Rosario|Tucum[aá]n|'
            r'Santa Fe|Mart[ií]nez|Salta|Mar del Plata|Hurlingham|Z[aá]rate|Argentina)',
            block, re.IGNORECASE
        )
        lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
        link_m = re.search(r'href="(/offres/[^"]+)"', block)
        lien = f"https://mon-vie-via.businessfrance.fr{link_m.group(1)}" if link_m else url
        uid_key = f"{titre}|{lieu}"
        if uid_key in processed:
            continue
        processed.add(uid_key)
        offers.append({
            "entreprise": "Business France / VIE",
            "titre": titre, "type": "VIE", "lieu": lieu,
            "source": "Business France", "url": lien,
            "date_detection": datetime.date.today().isoformat(),
        })

    if not offers:
        simple = re.findall(r'<a[^>]+href="(/offres/(\d+)[^"]*)"[^>]*>\s*([^<]+?)\s*</a>', html, re.IGNORECASE)
        seen = set()
        for path, offer_id, titre in simple:
            titre = titre.strip()
            if not titre or len(titre) < 5 or offer_id in seen:
                continue
            seen.add(offer_id)
            if is_excluded_offer(titre):
                continue
            offers.append({
                "entreprise": "Business France / VIE",
                "titre": titre, "type": "VIE", "lieu": "Argentine (à vérifier)",
                "source": "Business France",
                "url": f"https://mon-vie-via.businessfrance.fr{path}",
                "date_detection": datetime.date.today().isoformat(),
                "_needs_verification": True,
            })

    verified = []
    for o in offers:
        if o.pop("_needs_verification", False):
            detail_html, det_err = fetch_url(o["url"])
            if det_err or not is_argentina(detail_html):
                continue
            if is_excluded_country(detail_html[:2000]):
                continue
            loc_m = re.search(
                r'(?:Buenos Aires|Pilar|Córdoba|Cordoba|Mendoza|Rosario|Tucum[aá]n|Santa Fe|Mart[ií]nez|Salta)',
                detail_html, re.IGNORECASE
            )
            if loc_m:
                o["lieu"] = loc_m.group(0) + ", Argentine"
            time.sleep(0.5)
        verified.append(o)

    print(f"  → {len(verified)} offre(s) VIE trouvée(s) en Argentine")
    return verified


# ─── SOURCE B : LINKEDIN ─────────────────────────────────────────────────────

def scrape_linkedin_company(entreprise: str) -> list:
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={urllib.parse.quote(entreprise)}"
        f"&location=Argentina&f_TPR=r604800"
    )
    html, err = fetch_url(url, timeout=12)
    if err:
        return []

    offers = []
    job_cards = re.findall(
        r'<(?:div|li)[^>]*class="[^"]*(?:job-search-card|result-card|base-card)[^"]*"[^>]*>(.*?)</(?:div|li)>',
        html, re.DOTALL | re.IGNORECASE
    )
    for card in job_cards:
        title_m = re.search(
            r'<(?:h3|span)[^>]*class="[^"]*(?:base-search-card__title|job-result-card__title)[^"]*"[^>]*>([^<]+)</(?:h3|span)>',
            card, re.IGNORECASE
        )
        if not title_m:
            title_m = re.search(r'aria-label="([^"]+)"', card, re.IGNORECASE)
        if not title_m:
            continue
        titre = title_m.group(1).strip()
        if is_excluded_offer(titre):
            continue
        loc_m = re.search(
            r'<(?:span|div)[^>]*class="[^"]*(?:job-result-card__location|base-search-card__metadata)[^"]*"[^>]*>([^<]+)</(?:span|div)>',
            card, re.IGNORECASE
        )
        lieu = loc_m.group(1).strip() if loc_m else ""
        if not is_argentina(lieu) and not is_argentina(card):
            continue
        if is_excluded_country(lieu):
            continue
        link_m = re.search(r'href="(https://[^"]*linkedin\.com/jobs/view/[^"?]+)', card)
        lien = link_m.group(1) if link_m else url
        offers.append({
            "entreprise": entreprise,
            "titre": titre,
            "type": qualify_type(titre + " " + lieu),
            "lieu": lieu or "Argentine",
            "source": "LinkedIn", "url": lien,
            "date_detection": datetime.date.today().isoformat(),
        })
    return offers


def scrape_linkedin_all() -> list:
    print("\n📡 SOURCE B — LinkedIn Jobs...")
    all_offers = []
    for entreprise in LINKEDIN_SLUGS:
        try:
            offers = scrape_linkedin_company(entreprise)
            if offers:
                print(f"  ✅ {entreprise}: {len(offers)} offre(s)")
            else:
                print(f"  — {entreprise}: aucune offre visible")
            all_offers.extend(offers)
            time.sleep(1.0)
        except Exception as e:
            print(f"  ⚠️  {entreprise}: {e}")
    print(f"  → {len(all_offers)} offre(s) LinkedIn total")
    return all_offers


# ─── SOURCE C : SITES CARRIÈRES ───────────────────────────────────────────────

def scrape_loreal() -> list:
    url = "https://careers.loreal.com/en_US/jobs/SearchJobs?orgIds=67&alp_lang=en_US&location=Argentina&locationId=COUNTRY-AR&locationLevel=country"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  L'Oréal: {err}")
        return []
    offers = []
    job_matches = re.findall(r'"title"\s*:\s*"([^"]+)"[^}]{0,200}"location"\s*:\s*"([^"]+)"', html)
    for titre, lieu in job_matches:
        if not is_argentina(lieu) or is_excluded_offer(titre):
            continue
        offers.append({"entreprise": "L'Oréal Argentina", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "L'Oréal Careers", "url": url,
                        "date_detection": datetime.date.today().isoformat()})
    if not offers:
        cards = re.findall(r'(?:class="[^"]*(?:job|position|career)[^"]*"[^>]*>)(.*?)(?=class="[^"]*(?:job|position|career)[^"]*"|$)', html, re.DOTALL | re.IGNORECASE)
        for card in cards[:30]:
            h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', card)
            if not h_m:
                continue
            titre = h_m.group(1).strip()
            if is_excluded_offer(titre) or len(titre) < 4 or not is_argentina(card):
                continue
            loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba)', card, re.IGNORECASE)
            lieu = loc_m.group(0) if loc_m else "Argentina"
            offers.append({"entreprise": "L'Oréal Argentina", "titre": titre,
                            "type": qualify_type(titre), "lieu": lieu,
                            "source": "L'Oréal Careers", "url": url,
                            "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_sanofi() -> list:
    url = "https://jobs.sanofi.com/en/search-jobs?q=&location=Argentina"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  Sanofi: {err}")
        return []
    offers = []
    items = re.findall(r'<(?:li|div|article)[^>]*class="[^"]*(?:job|position|result)[^"]*"[^>]*>(.*?)</(?:li|div|article)>', html, re.DOTALL | re.IGNORECASE)
    for item in items:
        h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', item)
        if not h_m:
            continue
        titre = h_m.group(1).strip()
        if is_excluded_offer(titre) or len(titre) < 4 or not is_argentina(item):
            continue
        loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba|Martínez)', item, re.IGNORECASE)
        lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
        link_m = re.search(r'href="([^"]*(?:jobs\.sanofi|sanofi)[^"]*)"', item)
        lien = link_m.group(1) if link_m else url
        offers.append({"entreprise": "Sanofi Argentina", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "Sanofi Jobs", "url": lien,
                        "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_saint_gobain() -> list:
    url = "https://joinus.saint-gobain.com/es/results?query=argentina"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  Saint-Gobain: {err}")
        return []
    offers = []
    items = re.findall(r'<(?:li|div|article)[^>]*class="[^"]*(?:job|position|result|card)[^"]*"[^>]*>(.*?)</(?:li|div|article)>', html, re.DOTALL | re.IGNORECASE)
    for item in items:
        h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', item)
        if not h_m:
            continue
        titre = h_m.group(1).strip()
        if is_excluded_offer(titre) or len(titre) < 4 or not is_argentina(item):
            continue
        loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba)', item, re.IGNORECASE)
        lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
        link_m = re.search(r'href="([^"]*saint-gobain[^"]*)"', item, re.IGNORECASE)
        lien = link_m.group(1) if link_m else url
        offers.append({"entreprise": "Saint-Gobain", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "Saint-Gobain Careers", "url": lien,
                        "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_accor() -> list:
    url = "https://careers.accor.com/es/es/jobs?country=AR"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  Accor: {err}")
        return []
    offers = []
    items = re.findall(r'<(?:li|div|article)[^>]*class="[^"]*(?:job|position|result|card)[^"]*"[^>]*>(.*?)</(?:li|div|article)>', html, re.DOTALL | re.IGNORECASE)
    for item in items:
        h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', item)
        if not h_m:
            continue
        titre = h_m.group(1).strip()
        if is_excluded_offer(titre) or len(titre) < 4:
            continue
        loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba|Mendoza)', item, re.IGNORECASE)
        lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
        link_m = re.search(r'href="([^"]*careers\.accor[^"]*)"', item, re.IGNORECASE)
        lien = link_m.group(1) if link_m else url
        offers.append({"entreprise": "Accor", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "Accor Careers", "url": lien,
                        "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_stellantis() -> list:
    url = "https://careers.stellantis.com/"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  Stellantis: {err}")
        return []
    offers = []
    if is_argentina(html):
        items = re.findall(r'<(?:li|div|article)[^>]*class="[^"]*(?:job|position|result|card)[^"]*"[^>]*>(.*?)</(?:li|div|article)>', html, re.DOTALL | re.IGNORECASE)
        for item in items:
            if not is_argentina(item):
                continue
            h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', item)
            if not h_m:
                continue
            titre = h_m.group(1).strip()
            if is_excluded_offer(titre) or len(titre) < 4:
                continue
            loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba)', item, re.IGNORECASE)
            lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
            offers.append({"entreprise": "Stellantis", "titre": titre,
                            "type": qualify_type(titre), "lieu": lieu,
                            "source": "Stellantis Careers", "url": url,
                            "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_ldc() -> list:
    url = "https://www.ldc.com/ar/es/carreras/unete-a-ldc/"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  LDC: {err}")
        return []
    offers = []
    items = re.findall(r'<(?:li|div|article)[^>]*class="[^"]*(?:job|position|result|card|vacancy)[^"]*"[^>]*>(.*?)</(?:li|div|article)>', html, re.DOTALL | re.IGNORECASE)
    for item in items:
        h_m = re.search(r'<h[1-4][^>]*>([^<]+)</h[1-4]>', item)
        if not h_m:
            continue
        titre = h_m.group(1).strip()
        if is_excluded_offer(titre) or len(titre) < 4:
            continue
        loc_m = re.search(r'(?:Buenos Aires|Argentina|Pilar|Córdoba|Rosario)', item, re.IGNORECASE)
        lieu = loc_m.group(0) + ", Argentine" if loc_m else "Argentine"
        link_m = re.search(r'href="([^"]+)"', item)
        lien = link_m.group(1) if link_m else url
        if lien.startswith("/"):
            lien = "https://www.ldc.com" + lien
        offers.append({"entreprise": "Louis Dreyfus Company", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "LDC Careers", "url": lien,
                        "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_pernod_ricard() -> list:
    url = "https://pernodricard.wd3.myworkdayjobs.com/pernod-ricard"
    html, err = fetch_url(url)
    if err:
        print(f"  ⚠️  Pernod Ricard: {err}")
        return []
    offers = []
    json_m = re.findall(r'"jobTitle"\s*:\s*"([^"]+)"[^}]{0,500}"locationName"\s*:\s*"([^"]+)"', html)
    for titre, lieu in json_m:
        if not is_argentina(lieu) or is_excluded_offer(titre):
            continue
        offers.append({"entreprise": "Pernod Ricard", "titre": titre,
                        "type": qualify_type(titre), "lieu": lieu,
                        "source": "Pernod Ricard Careers", "url": url,
                        "date_detection": datetime.date.today().isoformat()})
    return offers


def scrape_career_sites() -> list:
    print("\n📡 SOURCE C — Sites carrières officiels...")
    all_offers = []
    scrapers = [
        ("L'Oréal", scrape_loreal),
        ("Sanofi", scrape_sanofi),
        ("Saint-Gobain", scrape_saint_gobain),
        ("Accor", scrape_accor),
        ("Stellantis", scrape_stellantis),
        ("Louis Dreyfus", scrape_ldc),
        ("Pernod Ricard", scrape_pernod_ricard),
    ]
    for name, fn in scrapers:
        try:
            offers = fn()
            if offers:
                print(f"  ✅ {name}: {len(offers)} offre(s)")
            else:
                print(f"  — {name}: aucune offre extraite")
            all_offers.extend(offers)
            time.sleep(0.8)
        except Exception as e:
            print(f"  ⚠️  {name}: erreur — {e}")
    print(f"  → {len(all_offers)} offre(s) sites officiels total")
    return all_offers


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🤖 Agent de veille — Argentine (entreprises françaises)")
    print(f"   {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    print("=" * 60)

    state = load_state()
    print(f"\n📂 {len(state['known_offers'])} offres connues")
    if state.get("last_run"):
        print(f"   Dernière exécution : {state['last_run'][:16]}")

    all_offers = []
    errors = []

    try:
        all_offers.extend(scrape_business_france())
    except Exception as e:
        errors.append(f"Business France: {e}")

    try:
        all_offers.extend(scrape_linkedin_all())
    except Exception as e:
        errors.append(f"LinkedIn: {e}")

    try:
        all_offers.extend(scrape_career_sites())
    except Exception as e:
        errors.append(f"Career sites: {e}")

    print(f"\n📊 Total collecté : {len(all_offers)} offre(s)")

    # Détecter les nouvelles offres
    known  = set(state.get("known_offers", []))
    new_jobs = []
    seen   = set()
    for job in all_offers:
        uid = build_uid(job["entreprise"], job["titre"], job["lieu"])
        if uid not in known and uid not in seen:
            seen.add(uid)
            new_jobs.append(job)

    print(f"🆕 Nouvelles offres : {len(new_jobs)}")
    for j in new_jobs:
        print(f"   • [{j['type']}] {j['titre']} — {j['entreprise']} ({j['lieu']})")

    # Discord
    print("\n📣 Envoi Discord...")
    if new_jobs:
        discord_offers([
            {
                "titre":      j["titre"],
                "entreprise": j["entreprise"],
                "lieu":       j["lieu"],
                "type":       j.get("type", "CDI"),
                "secteur":    SECTEURS.get(j["entreprise"], ""),
                "lien":       j.get("url", ""),
                "date":       j.get("date_detection", ""),
            }
            for j in new_jobs
        ])
    else:
        discord_rien_de_nouveau()

    save_state(state, new_jobs)

    print("\n" + "=" * 60)
    print("✅ Veille terminée")
    print(f"   Nouvelles : {len(new_jobs)}  |  Connues total : {len(state['known_offers'])}")
    if errors:
        for e in errors:
            print(f"   ⚠️  {e}")
    print("=" * 60)


if __name__ == "__main__":
    main()
