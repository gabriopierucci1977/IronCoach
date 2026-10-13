#!/usr/bin/env bash
set -Eeuo pipefail

cd /workspaces/IronCoach || exit 1
expected_branch='feature/beta-0.4-decision-memory'
if [[ "$(git branch --show-current)" != "$expected_branch" ]]; then
  echo "STOP: branch diversa da quella attesa: $(git branch --show-current)"
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'STOP: il worktree contiene modifiche locali; nessun file è stato toccato.'
  git status --short --branch
  exit 1
fi

targets=(
  backend/maintain_plan/runtime_recovery_adapter.py
  backend/maintain_plan/runtime_reported_problems_bridge.py
  tests/maintain_plan/test_runtime_reported_problems_bridge.py
  docs/BETA_0_4_HANDOFF.md
  docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md
  docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
)
backup="$(mktemp -d /tmp/ironcoach-runtime-wiring-backup.XXXXXX)"
patch_file="$(mktemp /tmp/ironcoach-runtime-wiring-patch.XXXXXX)"
committed=0
for target in "${targets[@]}"; do
  if [[ -e "$target" ]]; then
    mkdir -p "$backup/$(dirname "$target")"
    cp -p "$target" "$backup/$target"
  fi
done
cat > "$patch_file" <<'__PATCH_BELOW__'
diff --git a/backend/maintain_plan/runtime_recovery_adapter.py b/backend/maintain_plan/runtime_recovery_adapter.py
index ac040f1..93b43dc 100644
--- a/backend/maintain_plan/runtime_recovery_adapter.py
+++ b/backend/maintain_plan/runtime_recovery_adapter.py
@@ -1,8 +1,8 @@
-"""Pure adapter from explicit runtime recovery records to stability contracts.
+"""Adapter from explicit runtime recovery records to stability contracts.
 
-This module deliberately does not read the Garmin archive, perform I/O, or
-derive a recovery category from a numeric readiness/body-battery value.  The
-caller must provide the runtime timestamps and the subject-scoped context.
+Builders are pure. Provider entry points may attach a persisted reported-problems
+projection only with explicit opt-in. The caller provides scoped records and
+timestamps; numeric readiness/body-battery values never imply a recovery category.
 """
 
 from __future__ import annotations
@@ -18,6 +18,9 @@ from .runtime_stability_provider import (
     RuntimeStabilityProviderResult,
     provide_runtime_stability,
 )
+from .runtime_reported_problems_bridge import (
+    attach_persisted_reported_problems_projection,
+)
 from .stability_models import (
     ActualSessionBoundary,
     AnalyzerRef,
@@ -315,8 +318,11 @@ def provide_runtime_stability_from_recovery_records(
     provenance_ref: object,
     evaluation_id: object,
     baseline_record: object = None,
+    enable_reported_problems_projection: bool = False,
+    reported_problems_projection_id: str | None = None,
+    projection_database_path: object = None,
 ) -> RuntimeStabilityProviderResult:
-    """Adapt explicit records and run the existing pure stability provider."""
+    """Adapt explicit records; optionally attach one persisted projection."""
     value = build_runtime_stability_input(
         prescription_binding=prescription_binding,
         actual_session_boundary=actual_session_boundary,
@@ -327,6 +333,12 @@ def provide_runtime_stability_from_recovery_records(
         baseline_record=baseline_record,
     )
     try:
+        value = attach_persisted_reported_problems_projection(
+            value,
+            enabled=enable_reported_problems_projection,
+            projection_id=reported_problems_projection_id,
+            database_path=projection_database_path,
+        )
         return provide_runtime_stability(value, evaluation_id=evaluation_id)
     except ValueError as exc:
         if isinstance(exc, RuntimeRecoveryAdapterError):
@@ -343,8 +355,11 @@ def provide_runtime_stability_from_prescription_baseline(
     evaluated_at: object,
     provenance_ref: object,
     evaluation_id: object,
+    enable_reported_problems_projection: bool = False,
+    reported_problems_projection_id: str | None = None,
+    projection_database_path: object = None,
 ) -> RuntimeStabilityProviderResult:
-    """Run the provider from a captured baseline without re-analysis or I/O."""
+    """Use the captured baseline and optionally one persisted projection."""
     value = build_runtime_stability_input_from_prescription_baseline(
         baseline=baseline,
         actual_session_boundary=actual_session_boundary,
@@ -354,6 +369,12 @@ def provide_runtime_stability_from_prescription_baseline(
         provenance_ref=provenance_ref,
     )
     try:
+        value = attach_persisted_reported_problems_projection(
+            value,
+            enabled=enable_reported_problems_projection,
+            projection_id=reported_problems_projection_id,
+            database_path=projection_database_path,
+        )
         return provide_runtime_stability(value, evaluation_id=evaluation_id)
     except ValueError as exc:
         if isinstance(exc, RuntimeRecoveryAdapterError):
diff --git a/docs/BETA_0_4_HANDOFF.md b/docs/BETA_0_4_HANDOFF.md
index 3549b5a..32e74d4 100644
--- a/docs/BETA_0_4_HANDOFF.md
+++ b/docs/BETA_0_4_HANDOFF.md
@@ -1135,3 +1135,24 @@ Il retry con stesso `projection_id` e contenuto identico è idempotente; una
 divergenza semantica è rifiutata senza sovrascrittura. Il modulo resta
 default-off e non è collegato al runtime legacy. Il contratto è in
 `docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md`.
+
+## Wiring runtime reported-problems → stability — 13 ottobre 2026
+
+I due ingressi `provide_runtime_stability_from_recovery_records` e
+`provide_runtime_stability_from_prescription_baseline` ora possono consumare
+una proiezione persistita. Il chiamante deve passare
+`enable_reported_problems_projection=True`, un `reported_problems_projection_id`
+esplicito e `projection_database_path` riferito a un database esistente.
+
+Il nuovo bridge valida il contesto prima del lookup, carica solo quell'ID e
+controlla ownership e riferimento completo della sessione. Il repository
+verifica anche la coerenza di metadata e payload. Un errore blocca la chiamata;
+non viene scelta una proiezione alternativa. Il provider puro valuta la stessa
+proiezione e conserva `INSUFFICIENT_DATA` per finestre o controlli incompleti.
+
+Sono aggiunti test per il default disattivato senza accesso SQLite, lettura dopo
+riapertura del repository, entrambi gli ingressi runtime, ID/database mancanti,
+ownership e sessione errate, metadata alterati e finestra non consumabile.
+Questo checkpoint collega gli ingressi espliciti; l'attivazione nel runtime
+legacy e la pubblicazione del final outcome richiedono ancora un'integrazione
+successiva con le fonti canoniche.
diff --git a/docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md b/docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md
index 12ca992..5c33a61 100644
--- a/docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md
+++ b/docs/MAINTAIN_PLAN_REPORTED_PROBLEMS_PROJECTION_CONTRACT.md
@@ -13,5 +13,23 @@ e payload tipizzato serializzato.
 La persistenza è append-only e default-off: stesso `projection_id` e payload
 identico sono un retry idempotente; lo stesso ID con contenuto diverso viene
 rifiutato senza sovrascrittura. Nuove proiezioni devono usare un ID distinto.
-Il modulo non è collegato a `backend/main.py` e non modifica la valutazione
-stability esistente.
+Il modulo di cattura non è collegato a `backend/main.py`.
+
+## Consumo runtime opt-in
+
+`runtime_reported_problems_bridge.py` carica una sola proiezione persistita per
+ID esplicito e la inserisce in un `GeneralStabilityInput` validato. Il bridge
+è richiamato dai due ingressi `provide_runtime_stability_from_*` dell'adapter
+recovery quando `enable_reported_problems_projection=True`; il chiamante deve
+fornire anche `reported_problems_projection_id` e `projection_database_path`.
+
+Soggetto e riferimento completo della sessione devono coincidere con il
+contesto corrente. ID mancante o sconosciuto, database inesistente, ownership
+incoerente e metadata alterati interrompono la chiamata. Una proiezione già
+presente nell'input non viene sovrascritta. Il bridge non sceglie la proiezione
+più recente e non produce nuovo contenuto.
+
+La validità temporale e la disponibilità della proiezione sono valutate dal
+servizio stability esistente. Una finestra diversa o controlli del canale
+incompleti non diventano automaticamente `NO_KNOWN_ISSUE` o `STABLE`.
+Con il flag disattivato non avviene alcun accesso al database.
diff --git a/docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md b/docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
index 8b966b8..65669dd 100644
--- a/docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
+++ b/docs/MAINTAIN_PLAN_RUNTIME_RECOVERY_ADAPTER_CONTRACT.md
@@ -1,11 +1,12 @@
 # MAINTAIN_PLAN runtime recovery adapter contract
 
-Ultimo aggiornamento: 10 ottobre 2026
+Ultimo aggiornamento: 13 ottobre 2026
 
-`backend/maintain_plan/runtime_recovery_adapter.py` è un confine puro tra
-record recovery già disponibili al runtime e i contratti typed di
-MAINTAIN_PLAN. Non legge l'archivio, non usa rete o database e non viene
-importato dal percorso runtime attivo.
+`backend/maintain_plan/runtime_recovery_adapter.py` adatta i record recovery
+espliciti ai contratti typed di MAINTAIN_PLAN. I builder restano puri. Le due
+funzioni `provide_runtime_stability_from_*` possono leggere una proiezione
+reported-problems persistita quando il chiamante abilita il flag descritto
+sotto. Il modulo non viene importato dal percorso runtime legacy attivo.
 
 ## Input obbligatori
 
@@ -51,6 +52,32 @@ lo stesso `AnalyzerRef` della baseline, così la compatibilità confronta
 assessment prodotti dalla stessa identità dichiarata.
 
 `provide_runtime_stability_from_prescription_baseline` esegue poi il provider
-pure. Il bridge verifica il tipo della baseline, la sua validità e la
-coincidenza del `subject_ref` con la sessione; non legge la persistenza, non
-cerca record recenti e non attiva `backend/main.py`.
+pure. Il builder verifica il tipo della baseline, la sua validità e la
+coincidenza del `subject_ref` con la sessione.
+
+## Wiring della proiezione reported-problems persistita
+
+Entrambi gli ingressi `provide_runtime_stability_from_recovery_records` e
+`provide_runtime_stability_from_prescription_baseline` espongono tre nuovi
+parametri keyword opzionali:
+
+| Parametro | Default | Significato |
+| --- | --- | --- |
+| `enable_reported_problems_projection` | `False` | Solo `True` abilita il lookup. |
+| `reported_problems_projection_id` | `None` | ID esatto della proiezione già persistita. |
+| `projection_database_path` | `None` | Percorso del database SQLite esistente. |
+
+Con il flag disabilitato il bridge restituisce l'input senza aprire SQLite.
+Con il flag abilitato `runtime_reported_problems_bridge.py` valida il contesto,
+carica la proiezione per ID, verifica metadata e payload tramite il repository
+e controlla che soggetto e riferimento completo della sessione coincidano.
+Il database deve esistere e l'ID deve risolversi; altrimenti la chiamata fallisce
+senza cercare una proiezione alternativa o generare una nuova evidenza.
+
+La proiezione viene inserita nell'input immutabile passato al provider puro.
+I controlli canonici su finestra degli eventi, cutoff, stato del canale e
+safety signal restano nella valutazione stability: una proiezione incompleta
+o riferita a una finestra diversa conserva `INSUFFICIENT_DATA`.
+
+Questo collegamento aggiunge la lettura al confine runtime esplicito. Non
+attiva `backend/main.py`, non interpreta eventi e non pubblica un final outcome.
diff --git a/backend/maintain_plan/runtime_reported_problems_bridge.py b/backend/maintain_plan/runtime_reported_problems_bridge.py
new file mode 100644
index 0000000..0af4eb8
--- /dev/null
+++ b/backend/maintain_plan/runtime_reported_problems_bridge.py
@@ -0,0 +1,78 @@
+"""Opt-in lookup of one persisted projection for a runtime stability input.
+
+The caller chooses the projection ID. No latest-projection discovery or event
+interpretation takes place here; the stability provider remains pure.
+"""
+
+from __future__ import annotations
+
+from dataclasses import replace
+from pathlib import Path
+
+from .repository import MaintainPlanRepository
+from .stability_models import GeneralStabilityInput
+from .stability_validators import validate_general_stability_input
+
+
+class ReportedProblemsRuntimeBridgeError(ValueError):
+    def __init__(self, errors, *, code="INPUT_INVALID"):
+        self.code = code
+        self.errors = tuple(errors)
+        super().__init__("; ".join(self.errors))
+
+
+def attach_persisted_reported_problems_projection(
+    stability_input: GeneralStabilityInput,
+    *,
+    enabled: bool = False,
+    projection_id: str | None = None,
+    database_path: str | Path | None = None,
+) -> GeneralStabilityInput:
+    """Attach exactly one caller-selected projection; disabled calls do no I/O."""
+    if enabled is not True:
+        return stability_input
+    if type(stability_input) is not GeneralStabilityInput:
+        raise ReportedProblemsRuntimeBridgeError(
+            ("stability_input must be a GeneralStabilityInput",)
+        )
+    if stability_input.reported_problems_projection is not None:
+        raise ReportedProblemsRuntimeBridgeError(
+            ("stability_input already has a reported-problems projection",)
+        )
+    errors = validate_general_stability_input(stability_input)
+    if errors:
+        raise ReportedProblemsRuntimeBridgeError(errors)
+    if type(projection_id) is not str or not projection_id.strip():
+        raise ReportedProblemsRuntimeBridgeError(
+            ("projection_id is required",), code="INPUT_MISSING"
+        )
+    if (database_path is None or not isinstance(database_path, (str, Path))
+            or not str(database_path).strip()):
+        raise ReportedProblemsRuntimeBridgeError(
+            ("database_path is required",), code="INPUT_MISSING"
+        )
+    if not Path(database_path).is_file():
+        raise ReportedProblemsRuntimeBridgeError(
+            ("projection database does not exist",), code="INPUT_MISSING"
+        )
+
+    # The repository checks row metadata, the stored payload and the ownership
+    # of its persisted session. Never substitute a projection from another run.
+    projection = MaintainPlanRepository(database_path).get_reported_problems_projection(projection_id)
+    if projection is None:
+        raise ReportedProblemsRuntimeBridgeError(
+            ("projection_id was not found",), code="INPUT_MISSING"
+        )
+    if projection.subject_ref != stability_input.prescription_binding.subject_ref:
+        raise ReportedProblemsRuntimeBridgeError(
+            ("reported-problems projection ownership does not match the prescription",)
+        )
+    if projection.actual_session_ref != stability_input.actual_session_boundary.actual_session_ref:
+        raise ReportedProblemsRuntimeBridgeError(
+            ("reported-problems projection does not match the exact actual session",)
+        )
+    attached = replace(stability_input, reported_problems_projection=projection)
+    errors = validate_general_stability_input(attached)
+    if errors:
+        raise ReportedProblemsRuntimeBridgeError(errors)
+    return attached
diff --git a/tests/maintain_plan/test_runtime_reported_problems_bridge.py b/tests/maintain_plan/test_runtime_reported_problems_bridge.py
new file mode 100644
index 0000000..cacea1d
--- /dev/null
+++ b/tests/maintain_plan/test_runtime_reported_problems_bridge.py
@@ -0,0 +1,214 @@
+"""End-to-end opt-in read of an already persisted reported-problems projection."""
+
+import sqlite3
+from dataclasses import replace
+from datetime import timedelta
+
+import pytest
+
+from backend.maintain_plan.repository import MaintainPlanRepository
+from backend.maintain_plan import runtime_reported_problems_bridge as projection_bridge
+from backend.maintain_plan.runtime_recovery_adapter import (
+    RuntimeRecoveryAdapterError,
+    provide_runtime_stability_from_prescription_baseline,
+    provide_runtime_stability_from_recovery_records,
+)
+from backend.maintain_plan.runtime_reported_problems_bridge import (
+    ReportedProblemsRuntimeBridgeError,
+    attach_persisted_reported_problems_projection,
+)
+from backend.maintain_plan.stability_models import (
+    EventBoundary, ReportedProblemsEventWindow, StabilityResult,
+)
+from tests.maintain_plan.fixtures import NOW, RUN_SESSION
+from tests.maintain_plan.test_general_stability_service import make_input
+from tests.maintain_plan.test_recovery_baseline_capture import baseline as make_baseline
+
+
+def _runtime_kwargs():
+    context = make_input()
+    return dict(
+        prescription_binding=replace(context.prescription_binding, baseline_assessment_ref=None),
+        actual_session_boundary=context.actual_session_boundary,
+        records=[], captured_at=context.evaluated_at,
+        evaluated_at=context.evaluated_at,
+        provenance_ref=context.provenance_ref,
+        evaluation_id="reported-runtime",
+    )
+
+
+def _store_projection(tmp_path, *, context=None, projection=None):
+    context = context or make_input()
+    projection = projection or context.reported_problems_projection
+    path = tmp_path / "reported.db"
+    repo = MaintainPlanRepository(path)
+    repo.create_actual_session(replace(
+        RUN_SESSION, session_id=context.actual_session_boundary.actual_session_ref.artifact_id,
+        subject_ref=projection.subject_ref,
+    ))
+    repo.acquire_reported_problems_projection(projection)
+    return path, projection
+
+
+def test_disabled_runtime_never_reads_or_creates_database(tmp_path, monkeypatch):
+    def fail_repository(*args, **kwargs):
+        raise AssertionError("disabled wiring must never open SQLite")
+    monkeypatch.setattr(projection_bridge, "MaintainPlanRepository", fail_repository)
+    path = tmp_path / "does-not-exist.db"
+    result = provide_runtime_stability_from_recovery_records(
+        **_runtime_kwargs(),
+        reported_problems_projection_id="projection",
+        projection_database_path=path,
+    )
+    assert result.stability_input.reported_problems_projection is None
+    assert result.evaluation.reported_problems.stability_result is StabilityResult.INSUFFICIENT_DATA
+    assert not path.exists()
+
+
+def test_enabled_runtime_uses_exact_projection_after_repository_restart(tmp_path):
+    path, projection = _store_projection(tmp_path)
+    result = provide_runtime_stability_from_recovery_records(
+        **_runtime_kwargs(),
+        enable_reported_problems_projection=True,
+        reported_problems_projection_id=projection.projection_id,
+        projection_database_path=path,
+    )
+    assert result.stability_input.reported_problems_projection == projection
+    assert result.evaluation.reported_problems.stability_result is StabilityResult.STABLE
+    assert result.evaluation.reported_problems.projection_ref.projection_id == projection.projection_id
+    # A second call constructs a new repository and produces the same answer.
+    assert provide_runtime_stability_from_recovery_records(
+        **_runtime_kwargs(),
+        enable_reported_problems_projection=True,
+        reported_problems_projection_id=projection.projection_id,
+        projection_database_path=path,
+    ) == result
+
+
+def test_enabled_baseline_bridge_uses_same_persisted_projection(tmp_path):
+    captured = make_baseline()
+    context = make_input()
+    boundary = replace(
+        context.actual_session_boundary,
+        subject_ref=captured.binding.subject_ref,
+        session_end=NOW + timedelta(hours=2),
+    )
+    evaluated = NOW + timedelta(hours=8)
+    projection = replace(
+        context.reported_problems_projection,
+        subject_ref=captured.binding.subject_ref,
+        event_window=ReportedProblemsEventWindow(
+            boundary.session_end, EventBoundary.EXCLUSIVE,
+            evaluated, EventBoundary.INCLUSIVE,
+        ),
+        checked_through_at=evaluated,
+    )
+    path, projection = _store_projection(
+        tmp_path, context=replace(context, actual_session_boundary=boundary), projection=projection,
+    )
+    result = provide_runtime_stability_from_prescription_baseline(
+        baseline=captured, actual_session_boundary=boundary,
+        records=[], captured_at=evaluated, evaluated_at=evaluated,
+        provenance_ref=context.provenance_ref, evaluation_id="baseline-with-projection",
+        enable_reported_problems_projection=True,
+        reported_problems_projection_id=projection.projection_id,
+        projection_database_path=path,
+    )
+    assert result.stability_input.baseline_assessment == captured.assessment
+    assert result.evaluation.reported_problems.stability_result is StabilityResult.STABLE
+
+
+def test_missing_projection_and_database_fail_closed_without_creating_files(tmp_path):
+    path = tmp_path / "absent.db"
+    for overrides in (
+        {"projection_database_path": path},
+        {"reported_problems_projection_id": "projection"},
+        {"reported_problems_projection_id": "projection", "projection_database_path": path},
+    ):
+        with pytest.raises(RuntimeRecoveryAdapterError):
+            provide_runtime_stability_from_recovery_records(
+                **_runtime_kwargs(), enable_reported_problems_projection=True, **overrides,
+            )
+    assert not path.exists()
+    path, _ = _store_projection(tmp_path)
+    with pytest.raises(RuntimeRecoveryAdapterError, match="not found"):
+        provide_runtime_stability_from_recovery_records(
+            **_runtime_kwargs(), enable_reported_problems_projection=True,
+            reported_problems_projection_id="unknown", projection_database_path=path,
+        )
+
+
+def test_foreign_owner_or_session_is_never_attached(tmp_path):
+    path, projection = _store_projection(tmp_path)
+    kwargs = _runtime_kwargs()
+    foreign_owner = replace(
+        kwargs["prescription_binding"], subject_ref="foreign-athlete",
+    )
+    with pytest.raises(RuntimeRecoveryAdapterError, match="ownership"):
+        provide_runtime_stability_from_recovery_records(
+            **{**kwargs, "prescription_binding": foreign_owner,
+               "actual_session_boundary": replace(kwargs["actual_session_boundary"],
+                                                   subject_ref="foreign-athlete")},
+            enable_reported_problems_projection=True,
+            reported_problems_projection_id=projection.projection_id,
+            projection_database_path=path,
+        )
+    other_session = replace(
+        kwargs["actual_session_boundary"],
+        actual_session_ref=replace(projection.actual_session_ref, artifact_id="another-session"),
+    )
+    with pytest.raises(RuntimeRecoveryAdapterError, match="exact actual session"):
+        provide_runtime_stability_from_recovery_records(
+            **{**kwargs, "actual_session_boundary": other_session},
+            enable_reported_problems_projection=True,
+            reported_problems_projection_id=projection.projection_id,
+            projection_database_path=path,
+        )
+
+
+def test_corrupt_stored_metadata_and_stale_window_are_not_promoted(tmp_path):
+    context = make_input()
+    old = replace(
+        context.reported_problems_projection,
+        event_window=replace(context.reported_problems_projection.event_window,
+                             end_at=context.evaluated_at - timedelta(minutes=1)),
+    )
+    path, projection = _store_projection(tmp_path, projection=old)
+    result = provide_runtime_stability_from_recovery_records(
+        **_runtime_kwargs(), enable_reported_problems_projection=True,
+        reported_problems_projection_id=projection.projection_id,
+        projection_database_path=path,
+    )
+    assert result.evaluation.reported_problems.stability_result is StabilityResult.INSUFFICIENT_DATA
+    with sqlite3.connect(path) as connection:
+        connection.execute(
+            "UPDATE maintain_plan_reported_problems_projections SET result='ISSUE_REPORTED' "
+            "WHERE projection_id=?", (projection.projection_id,),
+        )
+    with pytest.raises(RuntimeRecoveryAdapterError, match="metadata"):
+        provide_runtime_stability_from_recovery_records(
+            **_runtime_kwargs(), enable_reported_problems_projection=True,
+            reported_problems_projection_id=projection.projection_id,
+            projection_database_path=path,
+        )
+
+
+def test_bridge_rejects_replacing_an_existing_projection(tmp_path):
+    path, projection = _store_projection(tmp_path)
+    with pytest.raises(ReportedProblemsRuntimeBridgeError, match="already has"):
+        attach_persisted_reported_problems_projection(
+            make_input(), enabled=True, projection_id=projection.projection_id,
+            database_path=path,
+        )
+
+
+def test_invalid_context_is_rejected_before_repository_access(tmp_path, monkeypatch):
+    def fail_repository(*args, **kwargs):
+        raise AssertionError("invalid input must never open SQLite")
+    monkeypatch.setattr(projection_bridge, "MaintainPlanRepository", fail_repository)
+    value = replace(make_input(projection=False), prescription_binding=None)
+    with pytest.raises(ReportedProblemsRuntimeBridgeError, match="prescription_binding"):
+        attach_persisted_reported_problems_projection(
+            value, enabled=True, projection_id="projection",
+            database_path=tmp_path / "ignored.db",
+        )
__PATCH_BELOW__
rollback() {
  rc="$1"
  set +e
  if [[ "$committed" -eq 0 ]]; then
    git restore --staged -- "${targets[@]}" 2>/dev/null || true
    for target in "${targets[@]}"; do
      if [[ -e "$backup/$target" ]]; then
        mkdir -p "$(dirname "$target")"
        cp -p "$backup/$target" "$target"
      else
        rm -f -- "$target"
      fi
    done
    echo 'ROLLBACK=ESEGUITO'
    rm -rf "$backup"
  else
    echo 'COMMIT_CONSERVATO: il push può essere ripetuto.'
    echo "BACKUP=$backup"
  fi
  rm -f "$patch_file"
  git status --short --branch
  exit "$rc"
}
trap 'rollback "$?"' ERR

git apply --check "$patch_file"
git apply "$patch_file"
python -m compileall -q backend/maintain_plan/runtime_recovery_adapter.py \
  backend/maintain_plan/runtime_reported_problems_bridge.py \
  tests/maintain_plan/test_runtime_reported_problems_bridge.py
python -m pytest -q \
  tests/maintain_plan/test_runtime_reported_problems_bridge.py \
  tests/maintain_plan/test_runtime_recovery_adapter.py \
  tests/maintain_plan/test_reported_problems_persistence.py
python -m pytest -q
git diff --check
git add -- "${targets[@]}"
git commit -m 'feat: wire persisted reported-problems into runtime stability'
committed=1
git push origin "$expected_branch"
trap - ERR
rm -rf "$backup" "$patch_file"
echo 'RUNTIME_WIRING=COMPLETATO'
git status --short --branch
exit 0
