#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scene-claim -> EpistemicEnvelope projection (pure, stdlib-only, no I/O).

Direction:

    author-defined SceneEpistemicClaim values (SceneWithClaims.epistemic_claims)
            |
            v   (this module: build envelopes, nothing else)
    Character Core EpistemicEnvelope
            |
            v   select_visible_epistemic_context(...)   [NOT here]
    EpistemicContextSnapshot

This module does NOT:

- decide any temporal / perceiver / holder visibility (that lives ONLY in
  ``services.character_core.epistemics`` via the already-accepted selector);
- convert free-form Scene text (title / location / prior_events /
  current_situation) into facts -- only explicitly authored claims project;
- reconcile contradictions -- two contradictory claims both project,
  independently;
- store anything, call anything, or touch the runtime event log.

The claim's ``claim_id`` is used as the envelope's single basis id: the claim
itself is the authored source of the fact. All other fields carry verbatim.
"""

from __future__ import annotations

from typing import Tuple

from services.character_core.epistemics import EpistemicEnvelope, EpistemicEnvelopeError

from .scene import Scene, SceneEpistemicClaim

__all__ = [
    "SceneEpistemicBridgeError",
    "project_scene_claim",
    "project_scene_claims",
]


class SceneEpistemicBridgeError(RuntimeError):
    """Deterministic fail-closed error raised by the scene-claim bridge.

    ``code`` is one of: ``unsupported_claim_input``, ``invalid_claim``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def project_scene_claim(claim: SceneEpistemicClaim) -> EpistemicEnvelope:
    """Project ONE author-defined scene claim into an EpistemicEnvelope.

    Pure projection: every claim field is carried verbatim; the claim id is
    the basis id. No visibility decision is made here -- perceiver and
    temporal windows are evaluated later by the Character Core selector.
    """
    if not isinstance(claim, SceneEpistemicClaim):
        raise SceneEpistemicBridgeError(
            "unsupported_claim_input",
            "scene claims must be SceneEpistemicClaim values "
            "(free-form scene text is never auto-mapped to an epistemic kind)",
        )
    try:
        return EpistemicEnvelope(
            meaning=claim.meaning,  # verbatim
            epistemic_kind=claim.epistemic_kind,
            provenance=claim.provenance,
            basis_event_ids=(claim.claim_id,),
            confidence=claim.confidence,
            holder_id=claim.holder_id,
            perceiver_ids=claim.perceiver_ids,
            valid_from_seq=claim.valid_from_seq,
            valid_to_seq=claim.valid_to_seq,
        )
    except EpistemicEnvelopeError as exc:
        # SceneEpistemicClaim validation already mirrors the envelope contract,
        # so this is defence-in-depth: fail closed, never guess.
        raise SceneEpistemicBridgeError("invalid_claim", str(exc)) from exc


def project_scene_claims(scene) -> Tuple[EpistemicEnvelope, ...]:
    """Project a scene's ``epistemic_claims`` into envelopes, in input order.

    ``None`` or a scene without claims yields ``()`` -- behaviour identical to
    having no claim layer at all. Free-form scene fields contribute nothing.
    """
    if scene is None:
        return ()
    if not isinstance(scene, Scene):
        raise SceneEpistemicBridgeError(
            "unsupported_claim_input", "scene must be a Scene"
        )
    claims = getattr(scene, "epistemic_claims", ()) or ()
    return tuple(project_scene_claim(claim) for claim in claims)
