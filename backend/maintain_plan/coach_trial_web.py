"""Minimal browser journey for an isolated hypothetical coach scenario."""

from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hmac
import os
import secrets
import webbrowser

from .coach_review import review_database, resolve_database_choice
from .coach_trial import available_activities, create_trial
from .coach_web import (_artifact_details, _trusted_origins, _valid_action,
                        configured_database_path)
from .runtime_matching_decision import DecisionStatus


DEFAULT_SUBJECT = "recO4aHGKSTexpXUC"


def trial_database_path(archive_path: str | Path) -> Path:
    archive = Path(archive_path)
    return archive.with_name(f"{archive.stem}.coach-trial{archive.suffix}")


def _action_rejection_reason(origin: str | None, expected_origin: str,
                             cookie: str, submitted_token: str,
                             server_token: str) -> str | None:
    """Explain a strict request rejection without exposing either CSRF token."""
    allowed_origins = {expected_origin}
    if expected_origin.startswith("https://"):
        allowed_origins.add(f"{expected_origin}:443")
    if origin not in allowed_origins:
        return "origine HTTPS inattesa"
    cookies = dict(item.strip().split("=", 1) for item in cookie.split(";") if "=" in item)
    cookie_token = cookies.get("ironcoach_action", "")
    if not cookie_token:
        return "cookie di autorizzazione mancante; ricarica la pagina e riprova"
    if not hmac.compare_digest(cookie_token, server_token):
        return "cookie di autorizzazione scaduto; ricarica la pagina e riprova"
    if not submitted_token or not hmac.compare_digest(submitted_token, server_token):
        return "pagina scaduta; ricaricala e riprova"
    return None


def render_trial_page(subject: str, *, activities=(), review=None,
                      message: str = "", action_token: str = "") -> str:
    banner = ("<aside><strong>SCENARIO DI PROVA · PIANO IPOTETICO</strong><br>"
              "Il piano e la valutazione esistono solo in questo scenario: non sono "
              "fatti storici dell’atleta e non vengono inviati ad Airtable né salvati "
              "nell’archivio MAINTAIN_PLAN reale.</aside>")
    body = ["<h1>IronCoach · Laboratorio revisione coach</h1>", banner]
    if message:
        body.append(f'<p class="message">{escape(message)}</p>')
    if review is None:
        body.extend([
            '<p>Scegli attività Garmin storiche disponibili e scrivi tu gli obiettivi '
            'del piccolo piano. I valori svolti non precompilano durata o intensità.</p>',
            '<form method="post"><input type="hidden" name="operation" value="create">',
            f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">',
            f'<input type="hidden" name="subject" value="{escape(subject, quote=True)}">'])
        if not activities:
            body.append("<p>Nessuna attività Garmin di nuoto, bici o corsa disponibile. "
                        "Non vengono inventate attività mancanti.</p>")
        for index, activity in enumerate(activities):
            sports = " / ".join(activity.sports)
            body.append(
                '<fieldset><label><input type="checkbox" name="selected" '
                f'value="{index}"> Usa questa attività</label><br>'
                f'<strong>{escape(activity.start.isoformat())}</strong> · '
                f'{escape(sports)} · {escape(activity.source)}<br>'
                f'<input type="hidden" name="session_{index}" value="{escape(activity.session_id, quote=True)}">'
                f'<label>Sport del piano <select name="sport_{index}">' + "".join(
                    f'<option value="{escape(sport)}">{escape(sport)}</option>'
                    for sport in activity.sports) + '</select></label> '
                f'<label>Durata prevista (min) <input type="number" name="duration_{index}" min="1" step="1"></label> '
                f'<label>RPE previsto (1–10) <input type="number" name="rpe_{index}" min="1" max="10" step="0.5"></label>'
                '</fieldset>')
        if activities:
            body.append("<button>Crea scenario ipotetico</button>")
        body.append("</form>")
    else:
        body.append("<h2>Valutazione del solo scenario di prova</h2>")
        suspended_pairs = {pair for pair, _message in review.suspended_evaluations}
        for pair, suspended_message in review.suspended_evaluations:
            body.append(
                '<section class="warning"><b>Valutazione sospesa:</b> '
                f'{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)} · '
                f'{escape(suspended_message)}</section>')
        for pair, evaluation in review.completed_evaluations:
            body.append(f'<section><b>Valutazione salvata:</b> {escape(pair.prescription_snapshot_id)} '
                        f'← {escape(pair.session_id)} · {_evaluation_summary(evaluation)}</section>')
        if review.saved_pair is not None and review.evaluation is not None:
            pair = review.saved_pair
            body.append(f'<section><b>Valutazione appena salvata:</b> '
                        f'{escape(pair.prescription_snapshot_id)} ← {escape(pair.session_id)} · '
                        f'{_evaluation_summary(review.evaluation)}</section>')
        decision = review.decision
        # resolve_coach_choice retains the decision that authorised the write.
        # Once that write succeeded its candidates are historical, not live forms.
        candidates = (() if review.saved_pair is not None else tuple(
            candidate for candidate in decision.candidates
            if candidate not in suspended_pairs))
        for candidate in candidates:
            detail = _artifact_details(review, candidate.prescription_snapshot_id,
                                       candidate.session_id)
            body.append(
                '<form method="post" class="candidate">'
                f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                f'<input type="hidden" name="subject" value="{escape(subject, quote=True)}">'
                '<input type="hidden" name="operation" value="confirm">'
                f'<input type="hidden" name="prescription" value="{escape(candidate.prescription_snapshot_id, quote=True)}">'
                f'<input type="hidden" name="session" value="{escape(candidate.session_id, quote=True)}">'
                f'<b>Piano ipotetico:</b> {escape(candidate.prescription_snapshot_id)}<br>'
                f'<b>Attività Garmin:</b> {escape(candidate.session_id)} · '
                f'{escape(detail.get("activity_time", ""))}<br>'
                '<button>Conferma abbinamento nello scenario di prova</button></form>')
        if decision.status is DecisionStatus.NOT_EVALUABLE:
            body.append("<p>I dati non consentono un abbinamento. Nessuna seduta è "
                        "considerata automaticamente saltata.</p>")
        body.append('<p><a href="/">Nuovo scenario (non modifica l’archivio reale)</a></p>')
    style = ("body{font:17px system-ui;max-width:920px;margin:32px auto;padding:0 18px}"
             "aside{background:#fff3cd;border:2px solid #d99b00;padding:16px}"
             "fieldset,.candidate,section{margin:14px 0;padding:14px;border:1px solid #bbb}"
             "input,select,button{font:inherit;padding:6px;margin:5px}.message{background:#eef8ee;padding:10px}"
             ".warning{background:#fff3cd}")
    return ("<!doctype html><html lang=it><meta charset=utf-8>"
            "<title>IronCoach · Scenario ipotetico</title>"
            f"<style>{style}</style><body>{''.join(body)}</body></html>")


def _evaluation_summary(evaluation) -> str:
    """Render only conclusions supported by canonical observed dimensions."""
    overall = "dati insufficienti" if evaluation.overall is None else evaluation.overall.value
    insufficient = []
    for result in evaluation.component_results:
        if result.quantity is not None and result.quantity.status.value == "INSUFFICIENT_DATA":
            insufficient.append(
                "durata primaria osservata assente; l’eventuale durata Garmin nelle "
                "metriche secondarie non è trattata come equivalente")
        if result.intensity is not None and result.intensity.status.value == "INSUFFICIENT_DATA":
            insufficient.append("RPE osservato assente")
    details = ""
    if insufficient:
        details = ". <strong>Dati insufficienti:</strong> " + "; ".join(
            dict.fromkeys(insufficient))
    return escape(overall) + details


def make_trial_handler(archive_path: str, trial_path: str, *,
                       action_token: str | None = None, environment=None):
    token_state = {"value": action_token or secrets.token_urlsafe(32)}
    environment = dict(os.environ if environment is None else environment)

    class TrialHandler(BaseHTTPRequestHandler):
        def _origin(self):
            return _trusted_origins(self.server.server_address[1], environment).get(
                self.headers.get("Host", ""))

        def _send(self, page, status=200):
            payload = page.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            secure = "; Secure" if (self._origin() or "").startswith("https://") else ""
            self.send_header("Set-Cookie",
                             f"ironcoach_action={token_state['value']}; SameSite=Strict; HttpOnly{secure}")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self._origin() is None:
                self._send("Indirizzo locale non valido.", 400)
                return
            subject = parse_qs(urlparse(self.path).query).get(
                "subject", [DEFAULT_SUBJECT])[0]
            try:
                activities = available_activities(archive_path, subject)
                self._send(render_trial_page(subject, activities=activities,
                                             action_token=token_state["value"]))
            except Exception as error:
                self._send(render_trial_page(subject, message=f"Dati non utilizzabili: {error}",
                                             action_token=token_state["value"]), 400)

        def do_POST(self):
            if self._origin() is None:
                self._send("Indirizzo locale non valido.", 400)
                return
            values = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode())
            subject = values.get("subject", [DEFAULT_SUBJECT])[0]
            origin = self._origin()
            submitted_token = values.get("action_token", [""])[0]
            rejection = _action_rejection_reason(
                self.headers.get("Origin"), origin,
                self.headers.get("Cookie", ""), submitted_token, token_state["value"])
            # Keep the shared, hardened coach_web guard authoritative as well;
            # the detailed helper only supplies a safe explanation to the coach.
            if rejection is not None or not _valid_action(
                    self.headers.get("Origin"), origin,
                    self.headers.get("Cookie", ""), submitted_token, token_state["value"]):
                activities = available_activities(archive_path, subject)
                reason = rejection or "origine o autorizzazione non valida"
                self._send(render_trial_page(
                    subject, activities=activities,
                    message=f"Azione respinta: {reason}.",
                    action_token=token_state["value"]), 403)
                return
            try:
                if values.get("operation", [""])[0] == "create":
                    choices = tuple({
                        "session_id": values[f"session_{index}"][0],
                        "sport": values[f"sport_{index}"][0],
                        "duration_minutes": values[f"duration_{index}"][0],
                        "rpe": values[f"rpe_{index}"][0],
                    } for index in values.get("selected", ()))
                    create_trial(archive_path, trial_path, subject, choices)
                    review = review_database(trial_path, subject)
                    message = "Scenario ipotetico creato nell’archivio di prova separato."
                else:
                    resolved = resolve_database_choice(
                        trial_path, subject, values["prescription"][0], values["session"][0])
                    # Re-read authoritative persisted state: completed evaluations
                    # and every still-live candidate get freshly rendered forms.
                    review = review_database(trial_path, subject)
                    token_state["value"] = secrets.token_urlsafe(32)
                    if resolved.evaluation is None:
                        detail = resolved.evaluation_message or "valutazione non completata"
                        message = f"Abbinamento salvato nello scenario di prova; {detail}"
                    else:
                        message = "Abbinamento e valutazione salvati soltanto nello scenario di prova."
                self._send(render_trial_page(subject, review=review, message=message,
                                             action_token=token_state["value"]))
            except Exception as error:
                activities = available_activities(archive_path, subject)
                self._send(render_trial_page(subject, activities=activities,
                                             message=f"Scenario non salvato: {error}",
                                             action_token=token_state["value"]), 400)

        def log_message(self, *_args):
            return
    return TrialHandler


def run(open_browser: bool = True, subject_ref: str = DEFAULT_SUBJECT) -> None:
    archive = configured_database_path()
    trial = trial_database_path(archive)
    server = ThreadingHTTPServer(("127.0.0.1", 8765),
                                 make_trial_handler(archive, str(trial)))
    origin = next(iter(_trusted_origins(server.server_address[1]).values()))
    url = f"{origin}/?subject={subject_ref}"
    print(f"Scenario coach ipotetico pronto: {url}")
    if open_browser and not os.environ.get("CODESPACE_NAME"):
        webbrowser.open(url)
    server.serve_forever()
