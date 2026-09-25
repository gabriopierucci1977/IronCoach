"""Dependency-free local browser UI for the MAINTAIN_PLAN coach journey."""

from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import hmac
import os
import re
import secrets
import webbrowser

from backend.config import get_runtime_config
from dotenv import dotenv_values
from .coach_review import (
    database_review_readiness, retry_database_evaluation, review_database,
    resolve_database_choice,
)
from .runtime_matching_decision import DecisionStatus


def _artifact_details(review, prescription_id: str, session_id: str):
    return next((item for item in review.candidate_details
                 if item["prescription_id"] == prescription_id
                 and item["session_id"] == session_id), {})


def render_page(subject_ref: str = "", *, review=None, message: str = "",
                action_token: str = "") -> str:
    body = ["<h1>IronCoach · Revisione piano</h1>",
            "<p>Confronta gli allenamenti previsti con le attività importate già disponibili.</p>",
            '<form method="get"><label>ID atleta <input name="subject" required value="' +
            escape(subject_ref, quote=True) + '"></label><button>Esamina</button></form>']
    if message:
        body.append(f'<p class="message">{escape(message)}</p>')
    if review is not None:
        decision = review.decision
        for pair, suspended_message in review.suspended_evaluations:
            body.append(
                '<section class="warning"><strong>Attività sospesa:</strong> '
                f'{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)}<br>'
                f'{escape(suspended_message)}</section>')
            if suspended_message.startswith("Valutazione non completata"):
                body.append(
                    '<form method="post">'
                    f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                    f'<input type="hidden" name="subject" value="{escape(subject_ref, quote=True)}">'
                    f'<input type="hidden" name="prescription" value="{escape(pair.prescription_snapshot_id, quote=True)}">'
                    f'<input type="hidden" name="session" value="{escape(pair.session_id, quote=True)}">'
                    '<input type="hidden" name="operation" value="retry_evaluation">'
                    '<button>Riprova valutazione</button></form>')
        for pair, evaluation in review.completed_evaluations:
            overall = ("giudizio complessivo non disponibile"
                       if evaluation.overall is None else evaluation.overall.value)
            body.append(
                '<section class="completed"><strong>Abbinamento completato:</strong> '
                f'{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)}<br>'
                f'Conseguenza sul piano: {escape(overall)}</section>')
        body.append(f"<h2>Esito: {escape(decision.status.value)}</h2>")
        if review.saved_pair is not None:
            pair = review.saved_pair
            body.append(f"<p><strong>Corrispondenza salvata:</strong> "
                        f"{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)}</p>")
            if review.evaluation_message:
                body.append(f'<p class="warning">{escape(review.evaluation_message)}</p>')
        elif decision.status in {DecisionStatus.MATCHED,
                                DecisionStatus.CONFIRMATION_REQUIRED}:
            if decision.status is DecisionStatus.MATCHED:
                body.append("<p><strong>Corrispondenza univoca proposta.</strong> "
                            "Controllala e salvala esplicitamente.</p>")
            else:
                body.append("<p><strong>Quale attività corrisponde all’allenamento previsto?</strong> "
                            "Scegli soltanto se lo riconosci. Nessuna seduta è considerata saltata.</p>")
            suspended_pairs = {pair for pair, _ in review.suspended_evaluations}
            for candidate in decision.candidates:
                if candidate in suspended_pairs:
                    continue
                detail = _artifact_details(review, candidate.prescription_snapshot_id,
                                           candidate.session_id)
                body.append(
                    '<form method="post" class="candidate">'
                    f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                    f'<input type="hidden" name="subject" value="{escape(subject_ref, quote=True)}">'
                    f'<input type="hidden" name="prescription" value="{escape(candidate.prescription_snapshot_id, quote=True)}">'
                    f'<input type="hidden" name="session" value="{escape(candidate.session_id, quote=True)}">'
                    f'<b>Previsto:</b> {escape(candidate.prescription_snapshot_id)} · '
                    f'{escape(detail.get("planned_time", ""))}<br>'
                    f'<b>Attività:</b> {escape(candidate.session_id)} · '
                    f'{escape(detail.get("activity_time", ""))}<br>'
                    f'<b>Sport:</b> {escape(detail.get("sport", ""))} · '
                    f'<b>Sorgente:</b> {escape(detail.get("source", ""))}<br>'
                    '<button>Conferma questa corrispondenza</button></form>')
            body.append('<p><a href="/">Non lo so: non salvare nulla</a></p>')
        else:
            body.append("<p>I dati non consentono una conclusione affidabile. "
                        "Non è stato segnato alcun allenamento come saltato.</p>")
        if review.evaluation is not None:
            overall = review.evaluation.overall
            consequence = ("giudizio complessivo non disponibile per questa prescrizione"
                           if overall is None else overall.value)
            body.append(f"<h2>Conseguenza sul piano: {escape(consequence)}</h2>"
                        f"<p>Copertura: {escape(review.evaluation.evaluation_coverage.status.value)}</p>")
    style = "body{font:18px system-ui;max-width:850px;margin:40px auto;padding:0 20px}" \
            "input,button{font:inherit;padding:8px;margin:6px}.candidate{border:1px solid #bbb;padding:16px;margin:12px 0}" \
            ".message,.completed{background:#eef8ee;padding:12px}.warning{background:#fff3cd;padding:12px}"
    return "<!doctype html><html lang=it><meta charset=utf-8><title>IronCoach Coach</title>" \
           f"<style>{style}</style><body>{''.join(body)}</body></html>"


def _valid_action(origin: str | None, expected_origin: str, cookie: str,
                  submitted_token: str, server_token: str) -> bool:
    cookies = dict(item.strip().split("=", 1) for item in cookie.split(";") if "=" in item)
    cookie_token = cookies.get("ironcoach_action", "")
    allowed_origins = {expected_origin}
    if expected_origin.startswith("https://"):
        # Origin serialisation normally elides HTTPS's default port, while
        # clients and proxies may also send the equivalent explicit form.
        allowed_origins.add(f"{expected_origin}:443")
    return (origin in allowed_origins and
            hmac.compare_digest(cookie_token, server_token) and
            hmac.compare_digest(submitted_token, server_token))


def _trusted_origins(port: int, environment=None) -> dict[str, str]:
    """Return origins derived from the process environment, never the request."""
    environment = os.environ if environment is None else environment
    codespace = environment.get("CODESPACE_NAME")
    if not codespace:
        return {
            f"127.0.0.1:{port}": f"http://127.0.0.1:{port}",
            f"localhost:{port}": f"http://localhost:{port}",
        }

    forwarding_domain = environment.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "")
    hostname_part = re.compile(
        r"^[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$")
    if (not hostname_part.fullmatch(codespace)
            or not hostname_part.fullmatch(forwarding_domain)):
        raise RuntimeError("Ambiente Codespaces incompleto o non valido.")
    host = f"{codespace}-{port}.{forwarding_domain}".lower()
    origin = f"https://{host}"
    # The private Codespaces proxy terminates HTTPS and currently sends the
    # loopback authority to the application.  Associate that authority with
    # the public browser origin derived above: request headers (including
    # X-Forwarded-Host) must never be able to choose the accepted origin.
    # Keep the environment-derived authorities for proxies which preserve the
    # original Host, including its equivalent explicit HTTPS default port.
    return {
        f"127.0.0.1:{port}": origin,
        f"localhost:{port}": origin,
        host: origin,
        f"{host}:443": origin,
    }


def make_handler(database_path: str, *, action_token: str | None = None,
                 environment=None):
    token = action_token or secrets.token_urlsafe(32)
    environment = dict(os.environ if environment is None else environment)
    class CoachHandler(BaseHTTPRequestHandler):
        def _trusted_request_origin(self) -> str | None:
            port = self.server.server_address[1]
            allowed = _trusted_origins(port, environment)
            return allowed.get(self.headers.get("Host", ""))

        def _reject_untrusted_host(self) -> bool:
            if self._trusted_request_origin() is not None:
                return False
            payload = b"Indirizzo locale non valido."
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return True

        def _send(self, page: str, status: int = 200):
            payload = page.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
            self.send_header("X-Frame-Options", "DENY")
            secure = ("; Secure" if self._trusted_request_origin().startswith(
                "https://") else "")
            self.send_header(
                "Set-Cookie",
                f"ironcoach_action={token}; SameSite=Strict; HttpOnly{secure}")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self._reject_untrusted_host():
                return
            subject = parse_qs(urlparse(self.path).query).get("subject", [""])[0]
            try:
                if not subject:
                    self._send(render_page(action_token=token))
                    return
                readiness = database_review_readiness(database_path, subject)
                if not readiness.ready:
                    self._send(render_page(
                        subject, message=readiness.message(), action_token=token))
                    return
                review = review_database(database_path, subject)
                self._send(render_page(
                    subject, review=review, message=readiness.message(),
                    action_token=token))
            except Exception as error:
                self._send(render_page(subject, message=f"Dati non utilizzabili: {error}"), 400)

        def do_POST(self):
            if self._reject_untrusted_host():
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"))
            subject = values.get("subject", [""])[0]
            try:
                expected_origin = self._trusted_request_origin()
                if not _valid_action(
                        self.headers.get("Origin"), expected_origin,
                        self.headers.get("Cookie", ""),
                        values.get("action_token", [""])[0], token):
                    self._send(render_page(subject,
                        message="Azione respinta: origine o autorizzazione non valida.",
                        action_token=token), 403)
                    return
                prescription = values.get("prescription", [""])[0]
                session = values.get("session", [""])[0]
                if values.get("operation", [""])[0] == "retry_evaluation":
                    review = retry_database_evaluation(
                        database_path, subject, prescription, session)
                else:
                    review = resolve_database_choice(
                        database_path, subject, prescription, session)
                message = ("Scelta del coach salvata e piano valutato."
                           if review.evaluation is not None
                           else "Scelta del coach salvata.")
                self._send(render_page(subject, review=review, message=message,
                                       action_token=token))
            except Exception as error:
                self._send(render_page(subject, message=f"Scelta non salvata: {error}"), 400)

        def log_message(self, *_args):
            return
    return CoachHandler


def configured_database_path(project_root: str | Path | None = None) -> str:
    root = Path(project_root) if project_root is not None else Path(__file__).parents[2]
    added = []
    for name, value in dotenv_values(root / ".env").items():
        if value is not None and name not in os.environ:
            os.environ[name] = value
            added.append(name)
    try:
        config = get_runtime_config()
    finally:
        for name in added:
            os.environ.pop(name, None)
    database = Path(config.maintain_plan_database_path)
    if not database.is_absolute():
        database = root / database
    if not database.is_file():
        raise FileNotFoundError(
            f"Archivio MAINTAIN_PLAN configurato non trovato: {database}")
    return str(database)


def run(open_browser: bool = True, subject_ref: str | None = None) -> None:
    database_path = configured_database_path()
    if subject_ref is not None:
        readiness = database_review_readiness(database_path, subject_ref)
        print(readiness.message())
        if not readiness.ready:
            raise RuntimeError(readiness.message())
    server = ThreadingHTTPServer(("127.0.0.1", 8765), make_handler(database_path))
    origin = next(iter(_trusted_origins(server.server_address[1]).values()))
    label = ("Revisione coach pronta" if subject_ref is not None
             else "Pagina coach pronta per il controllo atleta")
    print(f"{label}: {origin}")
    if open_browser and not os.environ.get("CODESPACE_NAME"):
        webbrowser.open(origin + "/")
    server.serve_forever()
