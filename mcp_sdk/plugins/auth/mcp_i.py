"""
MCP-I (Model Context Protocol Identity) Integration
===================================================
Uses Ed25519 for cryptographically verifiable identities.
Enables agents to sign spatial interventions with non-repudiation.
"""

from __future__ import annotations

import base64
import time
import uuid

import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class AgentIdentity(BaseModel):
    """A sovereign DID-based identity for an agent."""

    did: str = Field(default_factory=lambda: f"did:mcp:{uuid.uuid4().hex[:12]}")
    alias: str
    public_key_b64: str
    authorized_by: str = "human_principal"

    # We don't store the private key in the model for security
    # In a real system, this would be in a HSM/Vault
    _private_key: ed25519.Ed25519PrivateKey | None = None

    class Config:
        arbitrary_types_allowed = True


class SignedIntervention(BaseModel):
    """A cryptographically signed record of an agent's intervention."""

    intervention_id: str
    did: str
    action: str
    target_resource: str
    timestamp: float = Field(default_factory=time.time)
    signature_b64: str


class MCPIdentityLayer:
    """
    Hardened Identity and credential management.
    Compliant with W3C DID and VC standards (Simplified).
    """

    def __init__(self, principal_did: str = "did:mcp:human_admin") -> None:
        self.principal_did = principal_did
        self._identities: dict[str, AgentIdentity] = {}
        self._private_keys: dict[str, ed25519.Ed25519PrivateKey] = {}

    def issue_identity(self, alias: str) -> AgentIdentity:
        """Issues a new verifiable identity with Ed25519 keys."""
        priv_key = ed25519.Ed25519PrivateKey.generate()
        pub_key = priv_key.public_key()

        pub_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        pub_b64 = base64.b64encode(pub_bytes).decode("utf-8")

        identity = AgentIdentity(
            alias=alias, public_key_b64=pub_b64, authorized_by=self.principal_did
        )

        self._identities[identity.did] = identity
        self._private_keys[identity.did] = priv_key

        logger.info("Sovereign identity issued", did=identity.did, alias=alias)
        return identity

    def sign_action(self, did: str, action: str, target: str) -> SignedIntervention:
        """Signs an action utilizing the identity's private key."""
        if did not in self._private_keys:
            raise ValueError(f"No private key found for DID: {did}")

        priv_key = self._private_keys[did]
        timestamp = time.time()

        # Canonical payload for signing
        payload = f"{did}|{action}|{target}|{timestamp}".encode()
        signature = priv_key.sign(payload)
        sig_b64 = base64.b64encode(signature).decode("utf-8")

        intervention = SignedIntervention(
            intervention_id=f"intv_{uuid.uuid4().hex[:8]}",
            did=did,
            action=action,
            target_resource=target,
            timestamp=timestamp,
            signature_b64=sig_b64,
        )

        logger.info(
            "Intervention signed via MCP-I (Ed25519)", intervention_id=intervention.intervention_id
        )
        return intervention

    def verify_intervention(self, intervention: SignedIntervention) -> bool:
        """Verifies an intervention's signature against the identity's public key."""
        if intervention.did not in self._identities:
            logger.warning("Verification failed: DID not found", did=intervention.did)
            return False

        identity = self._identities[intervention.did]
        pub_bytes = base64.b64decode(identity.public_key_b64)
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        payload = f"{intervention.did}|{intervention.action}|{intervention.target_resource}|{intervention.timestamp}".encode()
        sig_bytes = base64.b64decode(intervention.signature_b64)

        try:
            pub_key.verify(sig_bytes, payload)
            return True
        except Exception as e:
            logger.error("Signature verification failed", error=str(e))
            return False
