"""Offline preregistered inputs; no model outputs or provider execution."""
from dataclasses import replace

from services.character_lab.scene import SceneEpistemicClaim, new_scene, with_epistemic_claims

BASELINE_HEAD = "e890fe43c3008478879c408cc4c0ede3040ce832"
ACCEPTED_SOURCE_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
SHARED_USER_INPUT = "Кира, где нам искать синий конверт?"
AT_SEQ = 10
WORLD = "Синий конверт находится в шкафу."
BELIEF_A = "Синий конверт находится в ящике стола."
BELIEF_B = "Синий конверт находится на полке."
SHARED_SCENE = new_scene(
    title="Поиск конверта", location="Гостиная", participants=["Кира", "Андрей"],
    prior_events=[], current_situation="На столе лежит блокнот.",
    scene_id="kira-belief-perceiver-v1", created_at="2026-09-07T00:00:00+00:00",
)
_WORLD = SceneEpistemicClaim(
    claim_id="envelope-location", meaning=WORLD, epistemic_kind="WORLD_FACT",
    provenance="scene_authored", perceiver_ids=("andrey",), valid_from_seq=10,
)
_BELIEF = SceneEpistemicClaim(
    claim_id="kira-location-belief", meaning=BELIEF_A, epistemic_kind="CHARACTER_BELIEF",
    provenance="scene_authored", holder_id="kira", confidence=0.7, valid_from_seq=10,
)
PAIRS = {
    "belief": {
        "A": (_WORLD, _BELIEF),
        "B": (_WORLD, replace(_BELIEF, meaning=BELIEF_B)),
    },
    "perceiver": {
        "A": (_WORLD, _BELIEF),
        "B": (replace(_WORLD, perceiver_ids=("andrey", "kira")), _BELIEF),
    },
}


def scene_for(pair, arm):
    return with_epistemic_claims(SHARED_SCENE, PAIRS[pair][arm])
