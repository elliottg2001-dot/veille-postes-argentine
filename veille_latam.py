#!/usr/bin/env python3
"""
Agent de veille VIE — Amérique Latine
Source : API Business France · Argentine · Chili · Brésil
Deploy : GitHub Actions (toutes les 30 min, 24h/24)
"""

import json
import os
import urllib.request
import urllib.error
import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_URL      = "https://civiweb-api-prd.azurewebsites.net/api/Offers/search"
WEBHOOK_URLS = [w for w in [os.environ.get("DISCORD_WEBHOOK", "")] if w]
STATE_FILE   = Path(__file__).parent / "vie_latam_state.json"

PAYS = [
    {"code": "AR", "nom": "Argentine", "flag": "🇦🇷", "color": 3447003},
    {"code": "CL", "nom": "Chili",     "flag": "🇨🇱", "color": 15844367},
    {"code": "BR", "nom": "Brésil",    "flag": "🇧🇷", "color": 3066993},
]

EXCLUDED = ["banco de talentos", "talent pool", "brandstorm", "hackathon"]

# ─── STATE ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # Migration : ajoute last_digest si absent
        if "last_digest" not in state:
            state["last_digest"] = ""
        return state
    return {
        "known_offers": [],
        "last_run": "",
        "last_digest": "",
        "stats": {"AR": 0, "CL": 0, "BR": 0},
    }


def save_state(state: dict, new_jobs: list):
    for job in new_jobs:
        uid = build_uid(job)
        if uid not in state["known_offers"]:
            state["known_offers"].append(uid)
        state["stats"][job["pays_code"]] = state["stats"].get(job["pays_code"], 0) + 1
    state["last_run"] = datetime.datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ State — {len(state['known_offers'])} offres connues.")


def build_uid(job: dict) -> str:
    # Inclut l'ID offre + date de début de broadcast pour détecter les re-publications
    # d'une même offre (même titre/entreprise mais nouveau cycle de diffusion)
    broadcast = (job.get("start_broadcast", "") or "")[:10]  # YYYY-MM-DD
    offer_id  = job.get("offer_id", "")
    return f"{job['pays_code'].lower()}|{offer_id}|{broadcast}"

# ─── API ──────────────────────────────────────────────────────────────────────

def fetch_offers(pays_code: str) -> list[dict]:
    payload = json.dumps({
        "keyword": "",
        "countriesIds": [pays_code],
        "geographicZonesIds": ["3"],
        "missionTypeIds": ["VIE"],
        "pageNumber": 1,
        "pageSize": 100,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Origin":     "https://mon-vie-via.businessfrance.fr",
            "Referer":    "https://mon-vie-via.businessfrance.fr/",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️  Erreur API {pays_code}: {e}")
        return []

    today = datetime.date.today().isoformat()
    offers = []
    for item in data.get("result", []):
        titre           = (item.get("missionTitle") or "").strip()
        entreprise      = (item.get("organizationName") or "").strip()
        ville           = (item.get("cityName") or "").strip().title()
        duree           = item.get("missionDuration") or 0
        offer_id        = item.get("id")
        start_broadcast = (item.get("startBroadcastDate") or "")[:10]  # YYYY-MM-DD
        if not titre or not entreprise:
            continue
        if any(p in titre.lower() for p in EXCLUDED):
            continue
        offers.append({
            "pays_code":       pays_code,
            "entreprise":      entreprise,
            "titre":           titre,
            "ville":           ville,
            "duree_mois":      duree,
            "offer_id":        offer_id,
            "start_broadcast": start_broadcast,
            "url":             f"https://mon-vie-via.businessfrance.fr/offres/{offer_id}",
            "date_detection":  today,
        })
    return offers

# ─── DISCORD ──────────────────────────────────────────────────────────────────

def discord_send(payload: dict) -> bool:
    if not WEBHOOK_URLS:
        print("  ⚠️  Aucun DISCORD_WEBHOOK défini")
        return False
    ok = True
    for url in WEBHOOK_URLS:
        try:
            data = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"  ❌ Discord error: {e}")
            ok = False
    return ok


def send_digest(state: dict, all_offers: list):
    """Envoie un rapport matinal une fois par jour (premier run après 8h00)."""
    today     = datetime.date.today().isoformat()
    now_hour  = datetime.datetime.now().hour

    if state.get("last_digest") == today:
        return  # déjà envoyé aujourd'hui
    if now_hour < 8:
        return  # trop tôt, on attend 8h00

    counts = {p["code"]: 0 for p in PAYS}
    for o in all_offers:
        counts[o["pays_code"]] = counts.get(o["pays_code"], 0) + 1

    pays_lines = "  ".join(
        f"{p['flag']} {p['nom']} : **{counts[p['code']]}**" for p in PAYS
    )

    embed = {
        "title": "🌅  Rapport matinal — Agent VIE LatAm",
        "description": (
            f"L'agent tourne correctement toutes les 30 minutes.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pays_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📂  **{len(state['known_offers'])} offres** connues au total"
        ),
        "color": 9807270,  # gris bleuté discret
        "footer": {
            "text": (
                f"🤖 Agent VIE LatAm  ·  Business France  ·  "
                f"{datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}"
            )
        },
    }

    ok = discord_send({"username": "Agent VIE 🤖", "embeds": [embed]})
    if ok:
        state["last_digest"] = today
        print("  ✅ Digest quotidien envoyé")
    else:
        print("  ❌ Digest KO")


def send_notification(new_jobs: list):
    groupes = {p["code"]: [] for p in PAYS}
    for job in new_jobs:
        groupes[job["pays_code"]].append(job)

    pays_detectes = [
        f"{p['flag']} {p['nom']}" + (f" ×{len(groupes[p['code']])}" if len(groupes[p['code']]) > 1 else "")
        for p in PAYS if groupes[p["code"]]
    ]

    embeds = [{
        "title": f"🌎  {len(new_jobs)} nouveau(x) VIE — Amérique Latine",
        "description": (
            f"**{len(new_jobs)} offre(s) VIE** publiée(s) sur Business France !\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{'  ·  '.join(pays_detectes)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "color": 3066993,
        "footer": {"text": f"🤖 Agent VIE LatAm  ·  Business France  ·  {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}"},
    }]

    for p in PAYS:
        offres = groupes[p["code"]]
        if not offres:
            continue
        fields = []
        for job in offres:
            fields.append({
                "name": f"┌─  {job['titre']}",
                "value": (
                    f"🏢  **{job['entreprise']}**\n"
                    f"📍  {job['ville']}\n"
                    f"⏱️  {job['duree_mois']} mois\n\n"
                    f"🔗  {job['url']}"
                ),
                "inline": False,
            })
            if job != offres[-1]:
                fields.append({"name": "​", "value": "​", "inline": False})

        embeds.append({
            "title":  f"{p['flag']}  {p['nom']}  —  {len(offres)} offre(s) VIE",
            "color":  p["color"],
            "fields": fields,
        })

    ok = discord_send({"username": "Agent VIE 🤖", "embeds": embeds[:10]})
    print("  ✅ Discord OK" if ok else "  ❌ Discord KO")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"🌎 Agent VIE LatAm — {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    state = load_state()
    known = set(state.get("known_offers", []))
    print(f"📂 {len(known)} offres connues")

    all_offers = []
    for p in PAYS:
        print(f"  {p['flag']} {p['nom']}...", end=" ", flush=True)
        offers = fetch_offers(p["code"])
        for o in offers:
            o["pays"]      = p["nom"]
            o["pays_flag"] = p["flag"]
        print(f"{len(offers)} offre(s)")
        all_offers.extend(offers)

    new_jobs, seen = [], set()
    for job in all_offers:
        uid = build_uid(job)
        if uid not in known and uid not in seen:
            seen.add(uid)
            new_jobs.append(job)

    print(f"🆕 {len(new_jobs)} nouvelle(s) offre(s)")
    for j in new_jobs:
        print(f"   {j['pays_flag']} {j['titre']} — {j['entreprise']} ({j['ville']})")

    if new_jobs:
        print("📣 Envoi Discord...")
        send_notification(new_jobs)

    # Digest quotidien (une fois par jour après 8h00)
    send_digest(state, all_offers)

    save_state(state, new_jobs)
    print("✅ Terminé.")


if __name__ == "__main__":
    main()
