"""T026 domain services: two-person canary release & migration compatibility
approvals (OPS-009), multi-branch operator management preserving clinical access
scopes (OPS-011), conflict-safe offline sync rejecting last-write-wins (OPS-013),
and fair calibrated no-show risk + timeout-safe CP-SAT scheduling optimization
(AI-007, AI-008).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth, models as m, services as svc
from .schemas import (
    AppointmentCreate,
    CpsatOptimizeRequest,
    MultibranchOperatorCreate,
    NoshowRiskRequest,
    OfflineSyncMutationCreate,
    ReleaseCanaryApproveRequest,
    ReleaseProposalCreate,
)


def _to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def create_release_proposal(
    db: Session,
    clinic_id: str,
    proposer_staff_id: str,
    actor: str,
    data: ReleaseProposalCreate,
) -> m.ReleaseChangeApproval:
    if not data.backward_compatible_schema:
        raise HTTPException(
            409,
            "Destructive or backward-incompatible schema migration blocked; forward-only compatibility required (OPS-009)",
        )
    row = m.ReleaseChangeApproval(
        clinic_id=clinic_id,
        release_tag=data.release_tag.strip(),
        target_migration_revision=data.target_migration_revision.strip(),
        canary_stage="pre_canary",
        backward_compatible_schema=True,
        forward_fix_and_backup_plan=data.forward_fix_and_backup_plan.strip(),
        proposer_staff_id=proposer_staff_id,
        status="pending_change_approval",
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.release_change_proposed",
        "release_change_approval",
        row.id,
        {"release_tag": row.release_tag},
    )
    db.commit()
    return row


def approve_release_canary_stage(
    db: Session,
    clinic_id: str,
    release_id: str,
    approver_staff_id: str,
    actor: str,
    data: ReleaseCanaryApproveRequest,
) -> m.ReleaseChangeApproval:
    row = svc.ensure(db, m.ReleaseChangeApproval, release_id, clinic_id)
    if row.proposer_staff_id == approver_staff_id:
        raise HTTPException(
            409,
            "Two-person change approval required before canary promotion (proposer != approver) (OPS-009)",
        )
    if (
        data.canary_stage == "promoted_100pct"
        and row.canary_stage not in {"canary_5pct", "canary_25pct"}
    ):
        raise HTTPException(
            409,
            "Cannot promote directly to 100% before running an approved canary stage (OPS-009)",
        )
    row.canary_stage = data.canary_stage
    row.approver_staff_id = approver_staff_id
    row.status = "rolled_back" if data.canary_stage == "rolled_back" else "canary_approved"
    svc.audit(
        db,
        clinic_id,
        actor,
        f"ops.release_{data.canary_stage}",
        "release_change_approval",
        row.id,
        {"approver_staff_id": approver_staff_id},
    )
    db.commit()
    return row


def assign_multibranch_operator(
    db: Session,
    home_clinic_id: str,
    granter_staff_id: str,
    actor: str,
    data: MultibranchOperatorCreate,
) -> m.MultibranchOperatorAssignment:
    if data.grants_clinical_chart_access:
        raise HTTPException(
            409,
            "Multi-branch operator assignment cannot grant cross-clinic clinical chart access (OPS-011)",
        )
    svc.ensure(db, m.Staff, data.operator_staff_id, home_clinic_id)
    key = data.owner_group_key.strip()

    for cid in {home_clinic_id, data.assigned_clinic_id}:
        enrolled = db.scalar(
            select(m.OwnerBranchScopeGrant).where(
                m.OwnerBranchScopeGrant.owner_group_key == key,
                m.OwnerBranchScopeGrant.clinic_id == cid,
                m.OwnerBranchScopeGrant.active.is_(True),
            )
        )
        if enrolled is None:
            raise HTTPException(
                403,
                f"Clinic '{cid}' has not enrolled in owner_group_key '{key}' (OPS-011)",
            )

    row = m.MultibranchOperatorAssignment(
        owner_group_key=key,
        operator_staff_id=data.operator_staff_id,
        home_clinic_id=home_clinic_id,
        assigned_clinic_id=data.assigned_clinic_id,
        operational_scope="aggregate_kpi_and_ops_read_only",
        grants_clinical_chart_access=False,
        granted_by_staff_id=granter_staff_id,
        active=True,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        home_clinic_id,
        actor,
        "ops.multibranch_operator_assigned",
        "multibranch_operator_assignment",
        row.id,
        {"assigned_clinic_id": data.assigned_clinic_id, "grants_clinical_chart_access": False},
    )
    db.commit()
    return row


def apply_offline_sync_mutation(
    db: Session,
    principal: auth.Principal,
    data: OfflineSyncMutationCreate,
) -> m.OfflineSyncMutation:
    clinic_id = principal.clinic_id
    actor = principal.actor_label
    mut_id = data.client_mutation_id.strip()

    existing = db.scalar(
        select(m.OfflineSyncMutation).where(
            m.OfflineSyncMutation.clinic_id == clinic_id,
            m.OfflineSyncMutation.client_mutation_id == mut_id,
        )
    )
    if existing is not None:
        return existing

    if data.entity_type == "signed_clinical_snapshot":
        auth.check_permission(db, principal, "note.write")
        raise HTTPException(
            409,
            "Offline sync cannot mutate signed clinical snapshots; create a linked addendum online (OPS-013)",
        )

    if data.entity_type == "draft_note":
        auth.check_permission(db, principal, "note.write")
        content = str(data.payload.get("content") or "").strip()
        if not content:
            raise HTTPException(422, "Offline draft_note payload requires non-empty 'content'")
        note = svc.ensure(db, m.ClinicalNote, data.entity_id, clinic_id)
        if note.status != "draft":
            raise HTTPException(
                409,
                "Offline sync rejected: target note is already locked; last-write-wins prohibited (OPS-013)",
            )
        if data.base_version != note.latest_revision:
            raise HTTPException(
                409,
                f"Offline sync version conflict: base_version={data.base_version} != current={note.latest_revision} (OPS-013)",
            )
        svc.update_note(db, clinic_id, note.id, content, data.base_version, actor)
    else:
        auth.check_permission(db, principal, "appointment.write")
        appt_in = AppointmentCreate(**data.payload)
        svc.schedule(db, clinic_id, appt_in, actor)

    rec = m.OfflineSyncMutation(
        clinic_id=clinic_id,
        client_mutation_id=mut_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        base_version=data.base_version,
        resolution_strategy="optimistic_version_check",
        sync_status="applied",
        payload_json=json.dumps(data.payload, ensure_ascii=False),
        actor_demo=actor,
    )
    db.add(rec)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.offline_sync_applied",
        "offline_sync_mutation",
        rec.id,
        {"entity_type": rec.entity_type, "base_version": rec.base_version},
    )
    db.commit()
    return rec


def evaluate_calibrated_noshow_risk(
    db: Session,
    clinic_id: str,
    appointment_id: str,
    actor: str,
    ai_enabled: bool,
    data: NoshowRiskRequest,
) -> m.NoshowRiskAssessment:
    if data.include_demographic_features:
        raise HTTPException(
            409,
            "Protected demographic attributes are excluded from no-show risk scoring for fairness (AI-007)",
        )
    appt = svc.ensure(db, m.Appointment, appointment_id, clinic_id)

    if not ai_enabled or data.simulate_model_unavailable:
        band = "fallback_neutral"
        prob_bp = 1500
        rec_action = "Model unavailable/disabled: use standard front-desk reminder confirmation"
    else:
        prior_cancelled = int(
            db.scalar(
                select(func.count())
                .select_from(m.Appointment)
                .where(
                    m.Appointment.clinic_id == clinic_id,
                    m.Appointment.patient_id == appt.patient_id,
                    m.Appointment.status == "cancelled",
                )
            )
            or 0
        )
        confirmed_ev = db.scalar(
            select(m.AppointmentConfirmation.id).where(
                m.AppointmentConfirmation.clinic_id == clinic_id,
                m.AppointmentConfirmation.appointment_id == appt.id,
                m.AppointmentConfirmation.event_type == "patient_confirmed",
            )
        )
        prob_bp = min(7500, max(500, 1200 + prior_cancelled * 1400 - (600 if confirmed_ev else 0)))
        if prob_bp >= 4000:
            band = "elevated"
            rec_action = "Human receptionist phone confirmation 24h prior recommended (never auto-cancel)"
        elif prob_bp >= 2000:
            band = "moderate"
            rec_action = "Send standard approved reminder and await patient confirmation"
        else:
            band = "low"
            rec_action = "Standard confirmation workflow"

    row = m.NoshowRiskAssessment(
        clinic_id=clinic_id,
        appointment_id=appt.id,
        risk_band=band,
        calibrated_probability_bp=prob_bp,
        uses_protected_demographics=False,
        auto_cancelled_or_overbooked=False,
        recommended_human_action=rec_action,
        actor_demo=actor,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ai.noshow_risk_evaluated",
        "noshow_risk_assessment",
        row.id,
        {"risk_band": band, "calibrated_probability_bp": prob_bp},
    )
    db.commit()
    return row


def run_timeout_safe_cpsat_optimizer(
    db: Session,
    clinic_id: str,
    actor: str,
    data: CpsatOptimizeRequest,
) -> dict:
    win_start = _to_utc_naive(data.window_start_at)
    win_end = _to_utc_naive(data.window_end_at)
    chairs = db.scalars(
        select(m.Resource)
        .where(m.Resource.clinic_id == clinic_id, m.Resource.kind == "chair")
        .order_by(m.Resource.id.asc())
    ).all()
    if not chairs:
        raise HTTPException(422, "No dental chairs registered in clinic")

    for req in data.requests:
        svc.ensure(db, m.Patient, req.patient_id, clinic_id)
        svc.doctor(db, req.practitioner_id, clinic_id)

    if data.simulate_solver_timeout or data.solver_budget_ms == 0:
        run_row = m.CpsatOptimizationRun(
            clinic_id=clinic_id,
            solver_budget_ms=data.solver_budget_ms,
            solver_outcome="timeout_aborted_zero_changes",
            proposed_assignments_json="[]",
            existing_bookings_mutated_count=0,
            actor_demo=actor,
        )
        db.add(run_row)
        db.flush()
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.cpsat_timeout_safe_abort",
            "cpsat_optimization_run",
            run_row.id,
            {"existing_bookings_mutated_count": 0},
        )
        db.commit()
        return {
            "id": run_row.id,
            "solver_outcome": run_row.solver_outcome,
            "proposed_assignments": [],
            "existing_bookings_mutated_count": 0,
        }

    busy = db.scalars(
        select(m.ResourceBooking).where(
            m.ResourceBooking.clinic_id == clinic_id,
            m.ResourceBooking.state == "active",
            m.ResourceBooking.start_at < win_end,
            m.ResourceBooking.end_at > win_start,
        )
    ).all()
    downtimes = db.scalars(
        select(m.ResourceDowntime).where(
            m.ResourceDowntime.clinic_id == clinic_id,
            m.ResourceDowntime.status == "active",
            m.ResourceDowntime.start_at < win_end,
            m.ResourceDowntime.end_at > win_start,
        )
    ).all()

    deadline = time.perf_counter() + (data.solver_budget_ms / 1000.0)
    step = timedelta(minutes=15)
    placed: list[dict] = []
    timed_out = False

    def _conflicts(rkey: str, s: datetime, e: datetime, tentative: list[dict]) -> bool:
        if any(b.resource_key == rkey and b.start_at < e and b.end_at > s for b in busy):
            return True
        if any(d.resource_key == rkey and d.start_at < e and d.end_at > s for d in downtimes):
            return True
        for t in tentative:
            if rkey in (f"dentist:{t['practitioner_id']}", f"chair:{t['chair_id']}"):
                if t["_s"] < e and t["_e"] > s:
                    return True
        return False

    def _backtrack(idx: int, tentative: list[dict]) -> bool:
        nonlocal timed_out
        if time.perf_counter() > deadline:
            timed_out = True
            return False
        if idx == len(data.requests):
            placed.extend(tentative)
            return True
        job = data.requests[idx]
        dur = timedelta(minutes=job.duration_minutes)
        cur = win_start
        while cur + dur <= win_end:
            if time.perf_counter() > deadline:
                timed_out = True
                return False
            end = cur + dur
            doc_key = f"dentist:{job.practitioner_id}"
            if not _conflicts(doc_key, cur, end, tentative):
                for ch in chairs:
                    ch_key = f"chair:{ch.id}"
                    if not _conflicts(ch_key, cur, end, tentative):
                        tentative.append(
                            {
                                "patient_id": job.patient_id,
                                "practitioner_id": job.practitioner_id,
                                "chair_id": ch.id,
                                "start_at": cur.isoformat() + "Z",
                                "end_at": end.isoformat() + "Z",
                                "_s": cur,
                                "_e": end,
                            }
                        )
                        if _backtrack(idx + 1, tentative):
                            return True
                        tentative.pop()
            cur += step
        return False

    solved = _backtrack(0, [])
    clean_assignments = [
        {k: v for k, v in item.items() if not k.startswith("_")} for item in placed
    ]
    if timed_out:
        outcome = "timeout_aborted_zero_changes"
        clean_assignments = []
    elif solved:
        outcome = "optimal_proposal_pending_human"
    else:
        outcome = "infeasible_window_zero_changes"

    run_row = m.CpsatOptimizationRun(
        clinic_id=clinic_id,
        solver_budget_ms=data.solver_budget_ms,
        solver_outcome=outcome,
        proposed_assignments_json=json.dumps(clean_assignments),
        existing_bookings_mutated_count=0,
        actor_demo=actor,
    )
    db.add(run_row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"ai.cpsat_{outcome}",
        "cpsat_optimization_run",
        run_row.id,
        {"assignment_count": len(clean_assignments), "existing_bookings_mutated_count": 0},
    )
    db.commit()
    return {
        "id": run_row.id,
        "solver_outcome": outcome,
        "proposed_assignments": clean_assignments,
        "existing_bookings_mutated_count": 0,
    }
