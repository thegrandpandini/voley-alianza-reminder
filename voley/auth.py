"""Autenticación con Google Calendar, sin dependencias externas.

Flujo "installed app" (el mismo que usa cualquier app de escritorio):

1. Corres `python sync.py login` una sola vez en tu PC.
2. Se abre el navegador, eliges tu cuenta y aceptas.
3. Google devuelve un `code` a http://127.0.0.1:<puerto>/ y lo canjeamos
   por un `refresh_token`.
4. Guardamos `token.json`. Ese archivo es lo que usa GitHub Actions.

El `refresh_token` sirve para siempre, salvo que revoques el acceso o dejes
de usarlo 6 meses.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import config

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Permiso mínimo: ver y editar eventos. No leemos correos ni nada más.
SCOPE = "https://www.googleapis.com/auth/calendar.events"


class AuthError(RuntimeError):
    """Problema de credenciales / permisos."""


def load_client_secret(path: str | None = None) -> tuple[str, str]:
    """Lee el client_secret.json descargado de Google Cloud Console."""
    source = Path(path or config.CLIENT_SECRET_FILE)
    if not source.exists():
        raise AuthError(
            f"No encontré {source}.\n"
            "Descarga el JSON de tu cliente OAuth (tipo 'Desktop app') desde "
            "Google Cloud Console y guárdalo con ese nombre."
        )
    data = json.loads(source.read_text(encoding="utf-8"))
    block = data.get("installed") or data.get("web") or data
    client_id = block.get("client_id")
    client_secret = block.get("client_secret")
    if not client_id or not client_secret:
        raise AuthError(f"{source} no parece un client_secret.json válido.")
    return client_id, client_secret


def _post_form(url: str, fields: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise AuthError(f"Google rechazó la petición ({error.code}): {detail}") from error


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """Atiende el redirect de Google una sola vez."""

    server_version = "VoleyAuth/1.0"

    def do_GET(self) -> None:  # noqa: N802 (nombre impuesto por BaseHTTPRequestHandler)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/":
            self.send_response(404)
            self.end_headers()
            return

        query = urllib.parse.parse_qs(parsed.query)
        self.server.result = query  # type: ignore[attr-defined]

        ok = "code" in query
        message = (
            "Listo. Ya puedes cerrar esta ventana y volver a la terminal."
            if ok
            else f"Google devolvió un error: {query.get('error', ['desconocido'])[0]}"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;padding:3rem'>"
            f"<h2>{'✅ Autorización completa' if ok else '❌ No se autorizó'}</h2>"
            f"<p>{message}</p></body></html>".encode("utf-8")
        )

    def log_message(self, *args) -> None:
        """Silenciamos el log por defecto del servidor."""


def login(client_secret_file: str | None = None, token_file: str | None = None) -> dict:
    """Ejecuta el flujo OAuth completo y guarda token.json."""
    client_id, client_secret = load_client_secret(client_secret_file)
    verifier, challenge = _pkce_pair()

    httpd = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    httpd.result = {}  # type: ignore[attr-defined]
    port = httpd.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # necesario para recibir refresh_token
        "prompt": "consent",        # fuerza refresh_token aunque ya hayas aceptado
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    print("\nAbriendo el navegador para autorizar el acceso a tu calendario...")
    print(f"Si no se abre solo, copia y pega esta URL:\n\n{auth_url}\n")
    webbrowser.open(auth_url)

    httpd.handle_request()  # una sola petición, luego seguimos
    httpd.server_close()

    result = httpd.result  # type: ignore[attr-defined]
    if "code" not in result:
        raise AuthError(f"No se recibió el código de autorización: {result}")

    code = result["code"][0]
    tokens = _post_form(
        TOKEN_ENDPOINT,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )

    if "refresh_token" not in tokens:
        raise AuthError(
            "Google no devolvió refresh_token. Revoca el acceso de la app en "
            "https://myaccount.google.com/permissions y vuelve a intentar."
        )

    token = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
        "token": tokens.get("access_token"),
        "scope": tokens.get("scope"),
    }
    _write_token(token, token_file)
    print(f"✅ Credenciales guardadas en {token_file or config.TOKEN_FILE}")
    return token


def _write_token(token: dict, path: str | None = None) -> None:
    target = Path(path or config.TOKEN_FILE)
    target.write_text(json.dumps(token, indent=2), encoding="utf-8")
    try:  # permisos restrictivos donde el sistema lo permita
        os.chmod(target, 0o600)
    except OSError:
        pass


def load_token(path: str | None = None) -> dict:
    source = Path(path or config.TOKEN_FILE)
    if not source.exists():
        raise AuthError(
            f"No encontré {source}.\n"
            "Corre primero:  python sync.py login"
        )
    return json.loads(source.read_text(encoding="utf-8"))


def access_token() -> str:
    """Devuelve un access_token fresco usando el refresh_token guardado."""
    token = load_token()
    refreshed = _post_form(
        TOKEN_ENDPOINT,
        {
            "client_id": token["client_id"],
            "client_secret": token["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    if "access_token" not in refreshed:
        raise AuthError(f"No se pudo refrescar el token: {refreshed}")
    return refreshed["access_token"]
