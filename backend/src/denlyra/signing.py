"""T004 SignatureProvider abstraction and FakeSyntheticSignatureProvider test double.

IMPORTANT MEDICAL/LEGAL SAFETY RULE:
Real legal e-signature ('authenticated' status) is STRICTLY DISABLED in this synthetic
demonstrator until licensed Vietnamese dental & legal reviewers approve the provider,
identity proofing, and form mappings in docs/clinical/NEEDS_CLINICAL_REVIEW.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Protocol

from fastapi import HTTPException


@dataclass(frozen=True)
class SignatureReceipt:
    provider_id: str
    signer_staff_id: str
    canonical_sha256: str
    signature_hex: str
    signed_at_utc: str
    synthetic_only: bool = True


class SignatureProvider(Protocol):
    def sign_snapshot(
        self,
        canonical_bytes: bytes,
        signer_staff_id: str,
        clinic_id: str,
        simulate_failure: str | None = None,
    ) -> SignatureReceipt: ...

    def verify_receipt(
        self,
        canonical_bytes: bytes,
        receipt: SignatureReceipt,
        clinic_id: str,
    ) -> bool: ...


class FakeSyntheticSignatureProvider:
    """Deterministic test double for T004 negative and lifecycle testing.

    Never produces legally valid signatures; receipts carry synthetic_only=True.
    """

    provider_id = "fake-synthetic-test-double-v1"

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def _compute_sig(self, digest_hex: str, signer_staff_id: str, clinic_id: str) -> str:
        msg = f"{self.provider_id}:{clinic_id}:{signer_staff_id}:{digest_hex}".encode("utf-8")
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def sign_snapshot(
        self,
        canonical_bytes: bytes,
        signer_staff_id: str,
        clinic_id: str,
        simulate_failure: str | None = None,
    ) -> SignatureReceipt:
        if simulate_failure == "timeout":
            raise HTTPException(
                503,
                "Signature provider timed out; document snapshot remains unsealed (NEG-14)",
            )
        digest_hex = hashlib.sha256(canonical_bytes).hexdigest()
        sig_hex = self._compute_sig(digest_hex, signer_staff_id, clinic_id)
        if simulate_failure == "signature_mismatch":
            sig_hex = "0" * 64
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        receipt = SignatureReceipt(
            provider_id=self.provider_id,
            signer_staff_id=signer_staff_id,
            canonical_sha256=digest_hex,
            signature_hex=sig_hex,
            signed_at_utc=now_str,
            synthetic_only=True,
        )
        if not self.verify_receipt(canonical_bytes, receipt, clinic_id):
            raise HTTPException(
                409,
                "Signature provider verification failed on receipt; refusing to seal document",
            )
        return receipt

    def verify_receipt(
        self,
        canonical_bytes: bytes,
        receipt: SignatureReceipt,
        clinic_id: str,
    ) -> bool:
        actual_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        if not hmac.compare_digest(actual_sha256, receipt.canonical_sha256):
            return False
        expected_sig = self._compute_sig(
            receipt.canonical_sha256, receipt.signer_staff_id, clinic_id
        )
        return hmac.compare_digest(expected_sig, receipt.signature_hex)


def canonicalize_document_payload(payload: dict) -> tuple[str, bytes, str]:
    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    canonical_bytes = canonical_json.encode("utf-8")
    canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
    return canonical_json, canonical_bytes, canonical_sha256
