"""Dependency-free local browser UI for the MAINTAIN_PLAN coach journey."""

from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
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
from .rpe_feedback import capture_database_observed_rpe
from .repository import MaintainPlanRepository
from .session_coach import ai_comment, save_relation, session_facts
from .session_flow import build_export_prompt, list_sessions, session_detail, preview_imported_plan


def _artifact_details(review, prescription_id: str, session_id: str):
    return next((item for item in review.candidate_details
                 if item["prescription_id"] == prescription_id
                 and item["session_id"] == session_id), {})


def _source_label(session) -> str:
    """Describe only explicitly persisted activity sources."""
    sources = sorted({item.source.strip() for item in session.source_activities
                      if isinstance(item.source, str) and item.source.strip()})
    return ", ".join(sources) if sources else "fonte incerta"


def render_page(subject_ref: str = "", *, review=None, message: str = "",
                action_token: str = "", sessions=(), selected_session=None,
                ai_result=None, prescriptions=(), relation=None, page=1, pages=1,
                total=None, year=None, month=None, sport=None, import_preview=None) -> str:
    body = ["<h1>IronCoach · Le tue sedute</h1>",
            "<p>Esamina un allenamento svolto, con o senza un piano.</p>",
            '<form method="get"><label>ID atleta <input name="subject" required value="' +
            escape(subject_ref, quote=True) + '"></label><button>Esamina</button></form>']
    if message:
        body.append(f'<p class="message">{escape(message)}</p>')
    if subject_ref:
        body.append('<form method="get"><input type="hidden" name="subject" value="%s"><label>Anno <input name="year" value="%s"></label><label>Mese <input name="month" value="%s"></label><label>Sport <input name="sport" value="%s"></label><button>Filtra</button></form>' % (escape(subject_ref, quote=True), escape(str(year or '')), escape(str(month or '')), escape(str(sport or ''))))
        body.append('<section><h2>Importa piano JSON</h2><form method="post"><input type="hidden" name="operation" value="preview_plan"><input type="hidden" name="subject" value="%s"><input type="hidden" name="action_token" value="%s"><textarea name="plan_json" rows="4" cols="60" placeholder="Incolla qui il piano JSON per validarlo"></textarea><button>Valida e mostra anteprima</button></form></section>' % (escape(subject_ref, quote=True), escape(action_token, quote=True)))
    if sessions:
        body.append("<h2>Archivio allenamenti</h2>")
        for item in sessions:
            facts = session_facts(item)
            duration = ("durata non disponibile" if facts.duration_minutes is None
                        else f"{facts.duration_minutes:g} min")
            body.append(
                '<article class="candidate">'
                f'<b>{escape(facts.sport)}</b> · {escape(facts.start)} · {escape(duration)} · '
                f'fonte: {escape(_source_label(item))} '
                f'<a href="/?{urlencode({"subject": subject_ref, "session": item.session_id, "year": year or "", "month": month or "", "sport": sport or ""})}">Esamina</a></article>')
        body.append(f'<p>Pagina {page} di {pages}</p>')
        for target in (page - 1, page + 1):
            if 1 <= target <= pages:
                body.append(f'<a href="/?{urlencode({"subject": subject_ref, "page": target, "year": year or "", "month": month or "", "sport": sport or ""})}">Pagina {target}</a> ')
    if selected_session is not None:
        facts = session_facts(selected_session)
        detail = session_detail(selected_session)
        body.append(f'<section><h2>Sessione {escape(facts.session_id)}</h2>'
                    f'<h3>Dati osservati</h3><p>Sport: {escape(facts.sport)}; '
                    f'inizio: {escape(facts.start)}; durata: '
                    f'{escape("non disponibile" if facts.duration_minutes is None else str(facts.duration_minutes) + " min")}; '
                    f'fonte: {escape(_source_label(selected_session))}.</p></section>')
        body.append('<p>Metriche: %s · Dati mancanti: %s · Feedback: %s</p>' % (escape(", ".join(detail["metrics"]) or "nessuna"), escape(", ".join(detail["missing"]) or "nessuno"), escape(str(detail["feedback"] or "nessuno"))))
        prompt = build_export_prompt(selected_session, sessions)
        body.append('<button type="button" data-prompt="%s" onclick="navigator.clipboard.writeText(this.dataset.prompt);window.open(\'https://chatgpt.com/?q=\'+encodeURIComponent(this.dataset.prompt),\'_blank\');">Esporta dati verso ChatGPT</button>' % escape(prompt, quote=True))
        if relation is not None:
            body.append(f'<p class="completed"><strong>Scelta conservata:</strong> '
                        f'{escape(relation[0])}</p>')
        elif prescriptions:
            body.append('<section class="warning"><strong>Collegamento dubbio.</strong> '
                        '<p>Questa sessione appartiene al programma oppure è autonoma?</p>'
                        '<form method="post">'
                        f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                        f'<input type="hidden" name="subject" value="{escape(subject_ref, quote=True)}">'
                        f'<input type="hidden" name="session" value="{escape(facts.session_id, quote=True)}">'
                        '<input type="hidden" name="operation" value="save_relation">'
                        '<button name="relation" value="AUTONOMOUS">È autonoma</button>')
            for prescription in prescriptions:
                body.append(f'<button name="relation" value="PROGRAM:{escape(prescription.prescription_snapshot_id, quote=True)}">'
                            f'Appartiene a {escape(prescription.prescription_snapshot_id)}</button>')
            body.append('</form></section>')
        else:
            body.append('<p class="completed"><strong>Sessione autonoma:</strong> '
                        'non esistono prescrizioni da confrontare.</p>')
        if ai_result is not None and ai_result.available:
            body.append('<section class="ai"><h2>Parere IA</h2>'
                        f'<h3>Dati osservati</h3><p>{escape(ai_result.observed)}</p>'
                        f'<h3>Interpretazione</h3><p>{escape(ai_result.interpretation)}</p>'
                        f'<h3>Incertezze</h3><p>{escape(ai_result.uncertainties)}</p></section>')
        elif ai_result is not None:
            body.append('<section class="warning"><h2>Parere IA non disponibile</h2>'
                        f'<p>{escape(ai_result.unavailable_reason)}</p></section>')
        body.append('<section><strong>RPE facoltativo</strong><p>Se aiuta a interpretare la '
                    'seduta, indica lo sforzo percepito senza attribuirlo a Garmin o Strava.</p>'
                    '<form method="post">'
                    f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                    f'<input type="hidden" name="subject" value="{escape(subject_ref, quote=True)}">'
                    f'<input type="hidden" name="session" value="{escape(facts.session_id, quote=True)}">'
                    '<input type="hidden" name="operation" value="capture_session_rpe">'
                    '<input type="number" name="rpe" min="1" max="10"><button>Salva RPE</button>'
                    '</form></section>')
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
        for session_id, rpe_state in review.rpe_requests:
            if rpe_state.status == "VALUE":
                if rpe_state.attribution == "PORTAL_USER":
                    attribution = "dichiarato direttamente da te"
                elif rpe_state.attribution == "IMPORTED_SOURCE" and rpe_state.source:
                    attribution = f"fonte: {rpe_state.source}"
                else:
                    attribution = "provenienza non attribuibile con affidabilità"
                body.append(f'<section class="completed"><strong>RPE osservato:</strong> '
                            f'{escape(str(rpe_state.value))}/10 · {escape(attribution)}.'
                            '<p>Puoi correggerlo qui sotto se era errato.</p></section>')
            elif rpe_state.status == "OMITTED":
                body.append('<section class="completed"><strong>RPE non indicato.</strong> '
                            'Hai scelto di omettere il valore; puoi aggiungerlo in seguito.'
                            '</section>')
            if rpe_state.status == "UNANSWERED":
                guidance = ('Nessuna risposta è stata ancora data. I dati acquisiti non '
                            'contengono un RPE con significato e scala verificati.')
            elif rpe_state.status == "OMITTED":
                guidance = 'Puoi aggiungere ora un RPE oppure confermare di non indicarlo.'
            else:
                guidance = ('Inserisci un nuovo valore solo per correggere quello dichiarato; '
                            'la correzione sarà aggiunta allo storico.')
            body.append(
                '<section><strong>RPE osservato facoltativo</strong>'
                f'<p>{escape(guidance)} '
                'Puoi indicarlo da 1 a 10 oppure lasciare vuoto: il feedback disponibile resta '
                'visibile e la valutazione quantitativa può restare INSUFFICIENT_DATA.</p>'
                '<form method="post">'
                f'<input type="hidden" name="action_token" value="{escape(action_token, quote=True)}">'
                f'<input type="hidden" name="subject" value="{escape(subject_ref, quote=True)}">'
                f'<input type="hidden" name="session" value="{escape(session_id, quote=True)}">'
                '<input type="hidden" name="operation" value="capture_rpe">'
                '<label>RPE osservato (1–10) <input type="number" name="rpe" min="1" max="10" step="1"></label>'
                '<button>Salva risposta (anche vuota)</button></form></section>')
    if import_preview is not None:
        body.append('<section class="completed"><h3>Anteprima piano</h3><pre>%s</pre></section>' % escape(str(import_preview)))
    style = "body{font:18px system-ui;max-width:850px;margin:40px auto;padding:0 20px}" \
            "input,button{font:inherit;padding:8px;margin:6px}.candidate{border:1px solid #bbb;padding:16px;margin:12px 0}" \
            ".message,.completed{background:#eef8ee;padding:12px}.warning{background:#fff3cd;padding:12px}" \
            ".ai{background:#eef4ff;border-left:5px solid #315efb;padding:16px}a{margin-left:12px}"
    return "<!doctype html><html lang=it><meta charset=utf-8><title>IronCoach Coach</title>" \
           f"<style>{style}</style><body>{''.join(body)}</body></html>"


def _valid_origin(origin: str | None, expected_origin: str, *,
                  host: str | None = None,
                  forwarded_host: str | None = None,
                  forwarded_proto: str | None = None) -> bool:
    """Accept the public origin, or Codespaces' precisely identified rewrite."""
    allowed_origins = {expected_origin}
    if expected_origin.startswith("https://"):
        allowed_origins.add(f"{expected_origin}:443")
    if origin in allowed_origins:
        return True

    # Codespaces' web proxy can rewrite both the authority and Origin to its
    # loopback upstream.  Only recognise that form when the proxy also records
    # the environment-derived public authority and HTTPS scheme.  These exact
    # checks deliberately do not make arbitrary localhost origins trustworthy.
    public_authority = expected_origin.removeprefix("https://")
    return (
        expected_origin.startswith("https://")
        and host is not None
        and host.startswith(("localhost:", "127.0.0.1:"))
        and origin == f"https://{host}"
        and forwarded_host in {public_authority, f"{public_authority}:443"}
        and forwarded_proto == "https"
    )


def _valid_action(origin: str | None, expected_origin: str, cookie: str,
                  submitted_token: str, server_token: str, *,
                  host: str | None = None,
                  forwarded_host: str | None = None,
                  forwarded_proto: str | None = None) -> bool:
    cookies = dict(item.strip().split("=", 1) for item in cookie.split(";") if "=" in item)
    cookie_token = cookies.get("ironcoach_action", "")
    return (_valid_origin(origin, expected_origin, host=host,
                          forwarded_host=forwarded_host,
                          forwarded_proto=forwarded_proto) and
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
                 environment=None, configured_subject: str | None = None):
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
                repository = MaintainPlanRepository(database_path)
                query = parse_qs(urlparse(self.path).query)
                def integer(name):
                    raw = query.get(name, [""])[0]
                    return int(raw) if raw else None
                listing = list_sessions(repository, subject, page=integer("page") or 1,
                                        year=integer("year"), month=integer("month"),
                                        sport=query.get("sport", [None])[0] or None)
                sessions = listing.items
                if not sessions and listing.total == 0:
                    readiness = database_review_readiness(database_path, subject)
                    self._send(render_page(
                        subject, message=readiness.message(), action_token=token))
                    return
                session_id = parse_qs(urlparse(self.path).query).get("session", [""])[0]
                selected = repository.get_actual_session(session_id) if session_id else None
                if selected is not None and selected.subject_ref != subject:
                    selected = None
                prescriptions = repository.list_prescription_snapshots(subject)
                review = review_database(database_path, subject) if prescriptions else None
                stored_relation = (repository.get_session_relation(session_id)
                                   if selected is not None else None)
                if selected is not None and stored_relation is None:
                    mapping = next((item for item in repository.list_prescription_mappings()
                                    if item.actual_session_ref == session_id), None)
                    if mapping is not None:
                        stored_relation = ("PROGRAM", mapping.prescription_snapshot_ref)
                self._send(render_page(
                    subject, review=review,
                    message=f"{len(sessions)} attività disponibile/i.", action_token=token,
                    sessions=sessions, selected_session=selected, page=listing.page,
                    pages=listing.pages, total=listing.total, year=integer("year"),
                    month=integer("month"), sport=query.get("sport", [None])[0],
                    ai_result=(ai_comment(repository, subject, session_id)
                               if selected is not None else None),
                    prescriptions=prescriptions,
                    relation=stored_relation))
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
                        values.get("action_token", [""])[0], token,
                        host=self.headers.get("Host"),
                        forwarded_host=self.headers.get("X-Forwarded-Host"),
                        forwarded_proto=self.headers.get("X-Forwarded-Proto")):
                    self._send(render_page(subject,
                        message="Azione respinta: origine o autorizzazione non valida.",
                        action_token=token), 403)
                    return
                operation = values.get("operation", [""])[0]
                if operation == "preview_plan":
                    from .session_flow import preview_imported_plan
                    try:
                        preview = preview_imported_plan(values.get("plan_json", [""])[0])
                        message = "Piano valido: anteprima pronta."
                    except ValueError as error:
                        self._send(render_page(subject, message=f"JSON non valido: {error}", action_token=token))
                        return
                    self._send(render_page(subject, message=message, action_token=token,
                                           import_preview=preview))
                    return
                prescription = values.get("prescription", [""])[0]
                session = values.get("session", [""])[0]
                if operation in {"capture_rpe", "capture_session_rpe"}:
                    authoritative_subject = configured_subject or subject
                    capture_database_observed_rpe(
                        database_path, session_id=session,
                        submitted_rpe=values.get("rpe", [""])[0])
                    repository = MaintainPlanRepository(database_path)
                    sessions = repository.list_actual_sessions(authoritative_subject)
                    selected = repository.get_actual_session(session)
                    if operation == "capture_session_rpe":
                        self._send(render_page(
                            authoritative_subject, message="RPE osservato registrato.",
                            action_token=token, sessions=sessions, selected_session=selected,
                            ai_result=ai_comment(repository, authoritative_subject, session),
                            prescriptions=repository.list_prescription_snapshots(authoritative_subject),
                            relation=repository.get_session_relation(session)))
                        return
                    review = review_database(database_path, authoritative_subject)
                    subject = authoritative_subject
                    message = "RPE osservato registrato; i dati mancanti restano dichiarati come tali."
                elif operation == "save_relation":
                    raw_relation = values.get("relation", [""])[0]
                    relation, _, prescription_id = raw_relation.partition(":")
                    if relation == "PROGRAM":
                        resolve_database_choice(
                            database_path, subject, prescription_id, session)
                    save_relation(MaintainPlanRepository(database_path), subject, session,
                                  relation, prescription_id or None)
                    self.send_response(303)
                    self.send_header("Location", "/?" + urlencode(
                        {"subject": subject, "session": session}))
                    self.end_headers()
                    return
                elif operation == "retry_evaluation":
                    review = retry_database_evaluation(
                        database_path, subject, prescription, session)
                else:
                    review = resolve_database_choice(
                        database_path, subject, prescription, session)
                if operation != "capture_rpe":
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
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8765),
        make_handler(database_path, configured_subject=subject_ref))
    origin = next(iter(_trusted_origins(server.server_address[1]).values()))
    label = ("Revisione coach pronta" if subject_ref is not None
             else "Pagina coach pronta per il controllo atleta")
    print(f"{label}: {origin}")
    if open_browser and not os.environ.get("CODESPACE_NAME"):
        webbrowser.open(origin + "/")
    server.serve_forever()
