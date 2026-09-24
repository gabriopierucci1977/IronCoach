"""Dependency-free local browser UI for the MAINTAIN_PLAN coach journey."""

from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import webbrowser

from backend.config import get_runtime_config
from .coach_review import review_database, resolve_database_choice
from .runtime_matching_decision import DecisionStatus


def _artifact_details(review, prescription_id: str, session_id: str):
    return next((item for item in review.candidate_details
                 if item["prescription_id"] == prescription_id
                 and item["session_id"] == session_id), {})


def render_page(subject_ref: str = "", *, review=None, message: str = "") -> str:
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
        body.append(f"<h2>Esito: {escape(decision.status.value)}</h2>")
        if review.saved_pair is not None:
            pair = review.saved_pair
            body.append(f"<p><strong>Corrispondenza salvata:</strong> "
                        f"{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)}</p>")
            if review.evaluation_message:
                body.append(f'<p class="warning">{escape(review.evaluation_message)}</p>')
        elif decision.status is DecisionStatus.CONFIRMATION_REQUIRED:
            body.append("<p><strong>Quale attività corrisponde all’allenamento previsto?</strong> "
                        "Scegli soltanto se lo riconosci. Nessuna seduta è considerata saltata.</p>")
            for index, candidate in enumerate(decision.candidates):
                detail = _artifact_details(review, candidate.prescription_snapshot_id,
                                           candidate.session_id)
                body.append(
                    '<form method="post" class="candidate">'
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
            body.append(f"<h2>Conseguenza sul piano: {escape(review.evaluation.overall.value)}</h2>"
                        f"<p>Copertura: {escape(review.evaluation.evaluation_coverage.status.value)}</p>")
    style = "body{font:18px system-ui;max-width:850px;margin:40px auto;padding:0 20px}" \
            "input,button{font:inherit;padding:8px;margin:6px}.candidate{border:1px solid #bbb;padding:16px;margin:12px 0}" \
            ".message{background:#eef8ee;padding:12px}.warning{background:#fff3cd;padding:12px}"
    return "<!doctype html><html lang=it><meta charset=utf-8><title>IronCoach Coach</title>" \
           f"<style>{style}</style><body>{''.join(body)}</body></html>"


def make_handler(database_path: str):
    class CoachHandler(BaseHTTPRequestHandler):
        def _send(self, page: str, status: int = 200):
            payload = page.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            subject = parse_qs(urlparse(self.path).query).get("subject", [""])[0]
            try:
                review = review_database(database_path, subject) if subject else None
                self._send(render_page(subject, review=review))
            except Exception as error:
                self._send(render_page(subject, message=f"Dati non utilizzabili: {error}"), 400)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"))
            subject = values.get("subject", [""])[0]
            try:
                review = resolve_database_choice(database_path, subject,
                    values.get("prescription", [""])[0], values.get("session", [""])[0])
                message = ("Scelta del coach salvata e piano valutato."
                           if review.evaluation is not None
                           else "Scelta del coach salvata.")
                self._send(render_page(subject, review=review, message=message))
            except Exception as error:
                self._send(render_page(subject, message=f"Scelta non salvata: {error}"), 400)

        def log_message(self, *_args):
            return
    return CoachHandler


def run(open_browser: bool = True) -> None:
    config = get_runtime_config()
    server = ThreadingHTTPServer(("127.0.0.1", 8765),
                                 make_handler(config.maintain_plan_database_path))
    if open_browser:
        webbrowser.open("http://127.0.0.1:8765/")
    server.serve_forever()
