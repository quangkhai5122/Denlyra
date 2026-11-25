"""T026 two-person canary release & migration compatibility approvals (OPS-009),
multi-branch operator management preserving clinical access scopes (OPS-011),
conflict-safe offline sync rejecting last-write-wins (OPS-013), and fair calibrated
no-show risk + timeout-safe CP-SAT scheduling optimization (AI-007, AI-008).

Written BEFORE T026 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_canary_release_approvals_and_multibranch_operator_scope_isolation(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'rel_mbop.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner_a = _headers(client, "clinic_owner", clinic_id=CLINIC_A)
        med_dir_a = _headers(client, "medical_director", clinic_id=CLINIC_A)
        owner_b = _headers(client, "clinic_owner", clinic_id=CLINIC_B)

        pat_b = client.post(
            "/api/v1/patients",
            headers=owner_b,
            json={"display_name": "BN Chi Nhánh B Riêng Biệt", "birth_year": 1988},
        ).json()["id"]

        # Negative 1 (OPS-009): Backward-incompatible migration rejected -> 409
        assert (
            client.post(
                "/api/v1/ops/releases",
                headers=owner_a,
                json={
                    "release_tag": "v0.1.9-bad",
                    "target_migration_revision": "0013_terminology_templates_lab_reports_sync_and_ai",
                    "backward_compatible_schema": False,
                    "forward_fix_and_backup_plan": "Thiếu tương thích ngược",
                },
            ).status_code
            == 409
        )

        rel = client.post(
            "/api/v1/ops/releases",
            headers=owner_a,
            json={
                "release_tag": "v0.1.9-canary",
                "target_migration_revision": "0013_terminology_templates_lab_reports_sync_and_ai",
                "backward_compatible_schema": True,
                "forward_fix_and_backup_plan": "Chụp BackupManifest trước khi nâng cấp; sửa tiến nếu lỗi",
            },
        )
        assert rel.status_code == 201, rel.text
        rel_id = rel.json()["id"]

        # Negative 2 (OPS-009): Proposer cannot self-approve canary promotion -> 409
        assert (
            client.post(
                f"/api/v1/ops/releases/{rel_id}/approve-canary",
                headers=owner_a,
                json={"canary_stage": "canary_5pct"},
            ).status_code
            == 409
        )
        # Distinct medical_director approves canary_5pct -> 200
        app_rel = client.post(
            f"/api/v1/ops/releases/{rel_id}/approve-canary",
            headers=med_dir_a,
            json={"canary_stage": "canary_5pct"},
        )
        assert app_rel.status_code == 200
        assert app_rel.json()["status"] == "canary_approved"

        # OPS-011: Multi-branch operator assignment
        ctx_a = client.get("/api/v1/demo/context", headers=owner_a).json()
        owner_a_staff_id = next(s["id"] for s in ctx_a["staff"] if s["role"] == "clinic_owner")
        client.post(
            "/api/v1/org/branch-scope-grants",
            headers=owner_a,
            json={"owner_group_key": "ops-group-vn", "branch_id": "branch-main"},
        )
        client.post(
            "/api/v1/org/branch-scope-grants",
            headers=owner_b,
            json={"owner_group_key": "ops-group-vn", "branch_id": "branch-main"},
        )

        # Negative 3 (OPS-011): Attempting grants_clinical_chart_access=True rejected -> 409
        assert (
            client.post(
                "/api/v1/ops/multibranch-operators",
                headers=owner_a,
                json={
                    "owner_group_key": "ops-group-vn",
                    "operator_staff_id": owner_a_staff_id,
                    "assigned_clinic_id": CLINIC_B,
                    "grants_clinical_chart_access": True,
                },
            ).status_code
            == 409
        )

        op_assign = client.post(
            "/api/v1/ops/multibranch-operators",
            headers=owner_a,
            json={
                "owner_group_key": "ops-group-vn",
                "operator_staff_id": owner_a_staff_id,
                "assigned_clinic_id": CLINIC_B,
                "grants_clinical_chart_access": False,
            },
        )
        assert op_assign.status_code == 201, op_assign.text
        assert op_assign.json()["grants_clinical_chart_access"] is False

        # Clinical chart isolation preserved: owner_a STILL cannot read Clinic B patient chart -> 404
        assert client.get(f"/api/v1/patients/{pat_b}", headers=owner_a).status_code == 404


def test_conflict_safe_offline_sync_rejects_last_write_wins_and_locked_mutations(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'offline_sync.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Đồng Bộ Ngoại Tuyến", "birth_year": 1992},
        ).json()["id"]
        enc = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat, "practitioner_id": doc_id},
        ).json()["id"]
        note = client.post(
            f"/api/v1/encounters/{enc}/notes",
            headers=dentist,
            json={"content": "Bản nháp gốc v1"},
        ).json()["id"]

        # Negative 1 (OPS-013): last_write_wins strategy prohibited -> 422
        assert (
            client.post(
                "/api/v1/ops/offline-sync",
                headers=dentist,
                json={
                    "client_mutation_id": "mut-lww-001",
                    "entity_type": "draft_note",
                    "entity_id": note,
                    "base_version": 1,
                    "resolution_strategy": "last_write_wins",
                    "payload": {"content": "Ghi đè thô bạo"},
                },
            ).status_code
            == 422
        )

        # Valid optimistic offline sync v1 -> v2
        ok_sync = client.post(
            "/api/v1/ops/offline-sync",
            headers=dentist,
            json={
                "client_mutation_id": "mut-ok-001",
                "entity_type": "draft_note",
                "entity_id": note,
                "base_version": 1,
                "resolution_strategy": "optimistic_version_check",
                "payload": {"content": "Bản nháp đồng bộ hợp lệ v2"},
            },
        )
        assert ok_sync.status_code == 201, ok_sync.text
        assert ok_sync.json()["sync_status"] == "applied"

        # Negative 2 (OPS-013): Stale base_version=1 rejected with 409 (no silent overwrite of v2!)
        assert (
            client.post(
                "/api/v1/ops/offline-sync",
                headers=dentist,
                json={
                    "client_mutation_id": "mut-stale-002",
                    "entity_type": "draft_note",
                    "entity_id": note,
                    "base_version": 1,
                    "resolution_strategy": "optimistic_version_check",
                    "payload": {"content": "Bản cũ ngoại tuyến bị xung đột"},
                },
            ).status_code
            == 409
        )

        # Lock note -> offline sync targeting locked note rejected with 409!
        client.post(f"/api/v1/notes/{note}/demo-lock", headers=dentist)
        assert (
            client.post(
                "/api/v1/ops/offline-sync",
                headers=dentist,
                json={
                    "client_mutation_id": "mut-locked-003",
                    "entity_type": "draft_note",
                    "entity_id": note,
                    "base_version": 2,
                    "resolution_strategy": "optimistic_version_check",
                    "payload": {"content": "Thử sửa ghi chú đã khóa"},
                },
            ).status_code
            == 409
        )

        # Book slot 09:00..10:00 -> offline booking sync on overlapping slot rejected 409!
        client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-20T09:00:00+07:00",
                "end_at": "2026-12-20T10:00:00+07:00",
            },
        )
        assert (
            client.post(
                "/api/v1/ops/offline-sync",
                headers=receptionist,
                json={
                    "client_mutation_id": "mut-book-conflict-004",
                    "entity_type": "appointment_booking",
                    "entity_id": "offline-new-appt-1",
                    "base_version": 0,
                    "resolution_strategy": "optimistic_version_check",
                    "payload": {
                        "patient_id": pat,
                        "practitioner_id": doc_id,
                        "chair_id": chair_id,
                        "start_at": "2026-12-20T09:30:00+07:00",
                        "end_at": "2026-12-20T10:30:00+07:00",
                    },
                },
            ).status_code
            == 409
        )


def test_calibrated_fair_noshow_risk_and_timeout_safe_cpsat_optimizer(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'ai_sched.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Dự Báo No-Show & CP-SAT", "birth_year": 1995},
        ).json()["id"]
        appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-22T09:00:00+07:00",
                "end_at": "2026-12-22T10:00:00+07:00",
            },
        ).json()
        appt_id = appt["id"]

        # Negative 1 (AI-007): Demographic profiling prohibited -> 409
        assert (
            client.post(
                f"/api/v1/ai/appointments/{appt_id}/noshow-risk",
                headers=receptionist,
                json={"include_demographic_features": True},
            ).status_code
            == 409
        )

        # Safe fallback when model unavailable + regular calibrated score; appointment NEVER auto-cancelled
        fb = client.post(
            f"/api/v1/ai/appointments/{appt_id}/noshow-risk",
            headers=receptionist,
            json={"simulate_model_unavailable": True},
        )
        assert fb.status_code == 201, fb.text
        assert fb.json()["risk_band"] == "fallback_neutral"
        assert fb.json()["auto_cancelled_or_overbooked"] is False

        cal = client.post(
            f"/api/v1/ai/appointments/{appt_id}/noshow-risk",
            headers=receptionist,
            json={},
        )
        assert cal.status_code == 201, cal.text
        assert cal.json()["uses_protected_demographics"] is False
        assert cal.json()["auto_cancelled_or_overbooked"] is False

        # AI-008: CP-SAT timeout leaves existing bookings 100% untouched
        to_res = client.post(
            "/api/v1/ai/scheduling/cpsat-optimize",
            headers=receptionist,
            json={
                "window_start_at": "2026-12-22T09:00:00+07:00",
                "window_end_at": "2026-12-22T12:00:00+07:00",
                "solver_budget_ms": 50,
                "simulate_solver_timeout": True,
                "requests": [
                    {
                        "patient_id": pat,
                        "practitioner_id": doc_id,
                        "duration_minutes": 45,
                    }
                ],
            },
        )
        assert to_res.status_code == 201, to_res.text
        tb = to_res.json()
        assert tb["solver_outcome"] == "timeout_aborted_zero_changes"
        assert tb["existing_bookings_mutated_count"] == 0
        assert tb["proposed_assignments"] == []

        # Normal CP-SAT run finds non-overlapping assignment after 10:00+07:00 (03:00:00Z) with zero auto-mutations
        opt = client.post(
            "/api/v1/ai/scheduling/cpsat-optimize",
            headers=receptionist,
            json={
                "window_start_at": "2026-12-22T09:00:00+07:00",
                "window_end_at": "2026-12-22T12:00:00+07:00",
                "solver_budget_ms": 500,
                "simulate_solver_timeout": False,
                "requests": [
                    {
                        "patient_id": pat,
                        "practitioner_id": doc_id,
                        "duration_minutes": 45,
                    }
                ],
            },
        )
        assert opt.status_code == 201, opt.text
        ob = opt.json()
        assert ob["solver_outcome"] == "optimal_proposal_pending_human"
        assert ob["existing_bookings_mutated_count"] == 0
        assert len(ob["proposed_assignments"]) == 1
        assert ob["proposed_assignments"][0]["start_at"].startswith("2026-12-22T03:00:00")

        # Existing booking remains untouched
        appts_after = client.get("/api/v1/appointments", headers=receptionist).json()
        assert len(appts_after) == 1
        assert appts_after[0]["id"] == appt_id
        assert appts_after[0]["status"] == "confirmed"
