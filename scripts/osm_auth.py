#!/usr/bin/env python3
"""
GwadaBot — Authentification OAuth2 OSM (mode OOB)
Redirect URI à configurer sur OSM : urn:ietf:wg:oauth:2.0:oob

Usage:
  python scripts/osm_auth.py
"""

import secrets
import webbrowser
from pathlib import Path

import requests
from requests_oauthlib import OAuth2Session

# ── Endpoints ──────────────────────────────────────
AUTH_URL = "https://www.openstreetmap.org/oauth2/authorize"
TOKEN_URL = "https://www.openstreetmap.org/oauth2/token"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPES = ["read_prefs", "write_api", "write_notes"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _prompt(label: str) -> str:
    """Prompt non-vide."""
    while True:
        val = input(f"  {label}: ").strip()
        if val:
            return val
        print("  (vide, réessayez)")


def run_auth():
    print("=" * 58)
    print("  GwadaBot — Authentification OSM OAuth2")
    print("=" * 58)
    print(
        "\n  Vérifiez que votre application OSM a ce Redirect URI :\n"
        "    urn:ietf:wg:oauth:2.0:oob\n"
        "  https://www.openstreetmap.org/oauth2/applications\n"
    )

    client_id = _prompt("Votre OSM Client ID    ")
    client_secret = _prompt("Votre OSM Client Secret")

    print(f"\n  Client ID     : {client_id[:8]}... ({len(client_id)} car.)")
    print(f"  Client Secret : {client_secret[:4]}... ({len(client_secret)} car.)\n")

    # ── Générer l'URL d'autorisation ───────────────
    oauth = OAuth2Session(
        client_id=client_id,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        state=secrets.token_urlsafe(16),
    )
    auth_url, _ = oauth.authorization_url(AUTH_URL)

    print("=" * 58)
    print("  Ouverture du navigateur…")
    print("=" * 58)
    print(f"\n  URL : {auth_url}\n")
    webbrowser.open(auth_url)

    print(
        "  1. Connectez-vous à OSM\n"
        "  2. Cliquez « Autoriser »\n"
        "  3. Copiez le code affiché\n"
    )

    auth_code = _prompt("Collez le code ici")

    # ── Échanger le code contre un token ───────────
    print("\n  Échange du code contre un token…")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"\n  Erreur OSM ({resp.status_code}) : {resp.text}")
        print("  Le code expire après ~10 min, réessayez.")
        return

    access_token = resp.json().get("access_token")
    if not access_token:
        print(f"\n  Pas d'access_token : {resp.json()}")
        return

    # ── Sauvegarder ────────────────────────────────
    print("\n" + "=" * 58)
    print("  ✅ Token obtenu !")
    print("=" * 58)

    env_content = (
        f"OSM_CLIENT_ID={client_id}\n"
        f"OSM_CLIENT_SECRET={client_secret}\n"
        f"OSM_ACCESS_TOKEN={access_token}\n"
    )

    env_path = PROJECT_ROOT / ".env"
    try:
        env_path.write_text(env_content, encoding="utf-8")
        print(f"\n  Sauvegardé dans {env_path}")
        print("  ⚠️  Ne committez JAMAIS ce fichier !\n")
    except OSError as exc:
        print(f"\n  Impossible d'écrire .env : {exc}")
        print("  Copiez manuellement :\n")
        print(env_content)


if __name__ == "__main__":
    run_auth()
