#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core numeric-dimension semantics (RELATIONSHIP / PSYCHOLOGY).

This module defines WHAT a numeric runtime-state value MEANS -- it never
changes a value, never touches storage, and never performs automatic
evolution. It is a pure, deterministic, standard-library-only interpreter:

    numeric value  +  package-declared DimensionDefinition
        -> value + generic magnitude band + dimension-specific meaning
        -> a provider-ready semantic rendering

Design rules (owner decisions OD-MEM-EVO-04..07):

- Dimensions are CHARACTER-PACKAGE-DECLARED data. Core supplies only the
  schema, validation, the generic band mapping, and the rendering mechanism.
  Core MUST NOT contain a single character-specific dimension meaning.
- The five bands are generic magnitude/position bands
  (``VERY_LOW`` .. ``VERY_HIGH``) -- NOT "negative" / "positive", because a
  dimension measuring an internal burden makes that framing wrong.
- ``MISSING`` (never assessed) is permanently distinct from a real value of
  ``0``. It is modelled as :class:`DimensionValueStatus`, never as a sixth
  band. ``0`` has no universal meaning; its interpretation is whatever the
  :class:`DimensionDefinition` says the ``MID`` band means.

This module MUST NOT import ``services.character_lab`` or
``services.character_runtime`` -- Character Lab is a client of these
primitives, not the other way around.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

__all__ = [
    "StateDomain",
    "StateBand",
    "DimensionValueStatus",
    "NUMERIC_STATE_MIN",
    "NUMERIC_STATE_MAX",
    "BAND_THRESHOLDS",
    "REQUIRED_BANDS",
    "DimensionDefinitionError",
    "DimensionBandMeaning",
    "DimensionDefinition",
    "DimensionSet",
    "InterpretedDimensionState",
    "band_for_value",
    "interpret_value",
    "key_to_dimension_id",
    "interpret_state_entry",
    "semantic_state_line",
    "render_semantic_state",
]


# --------------------------------------------------------------------------
# Vocabularies
# --------------------------------------------------------------------------


class StateDomain(Enum):
    """The numeric semantic domains. ``FACT`` is deliberately absent -- it is
    free text, not a magnitude on a defined scale, and is never routed
    through this model."""

    RELATIONSHIP = "RELATIONSHIP"
    PSYCHOLOGY = "PSYCHOLOGY"


class StateBand(Enum):
    """Generic magnitude/position bands. NOT value judgements: ``VERY_HIGH``
    on one dimension can be desirable and undesirable on another -- the
    :class:`DimensionDefinition` carries that meaning, not this enum."""

    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class DimensionValueStatus(Enum):
    """Whether a dimension currently has an assessed value at all.

    ``MISSING`` is not a band and is never coerced to ``0`` -- "never
    assessed" and "assessed as zero" are different facts (OD-MEM-EVO-07).
    """

    KNOWN = "KNOWN"
    MISSING = "MISSING"


#: Canonical numeric range, matching ``services.character_runtime.state``.
NUMERIC_STATE_MIN = -100
NUMERIC_STATE_MAX = 100

#: Ordered, contiguous, inclusive band ranges (OD-MEM-EVO-05 default).
BAND_THRESHOLDS: Tuple[Tuple[StateBand, int, int], ...] = (
    (StateBand.VERY_LOW, -100, -60),
    (StateBand.LOW, -59, -20),
    (StateBand.MID, -19, 19),
    (StateBand.HIGH, 20, 59),
    (StateBand.VERY_HIGH, 60, 100),
)

#: Every band a :class:`DimensionDefinition` must give a meaning for.
REQUIRED_BANDS: Tuple[StateBand, ...] = tuple(b for b, _lo, _hi in BAND_THRESHOLDS)

#: Dimension id grammar. Intentionally identical to the current runtime
#: PSYCHOLOGY key grammar / the RELATIONSHIP key's dimension part -- this
#: module never loosens existing state-key validation.
_DIMENSION_ID_RE = re.compile(r"^[a-z0-9_]+$")
_CANONICAL_INT_RE = re.compile(r"^-?\d+$")


class DimensionDefinitionError(ValueError):
    """Fail-closed error for an invalid package-declared dimension definition
    or dimension set."""


# --------------------------------------------------------------------------
# DimensionDefinition
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensionBandMeaning:
    """One (band -> meaning) pair, the serializable unit of a definition."""

    band: StateBand
    meaning: str

    def __post_init__(self) -> None:
        if not isinstance(self.band, StateBand):
            raise DimensionDefinitionError("band must be a StateBand")
        if not isinstance(self.meaning, str) or not self.meaning.strip():
            raise DimensionDefinitionError("band meaning must be a non-empty string")


def _coerce_domain(domain) -> StateDomain:
    if isinstance(domain, StateDomain):
        return domain
    if isinstance(domain, str):
        try:
            return StateDomain(domain.strip())
        except ValueError:
            pass
    raise DimensionDefinitionError(
        f"domain must be one of {[d.value for d in StateDomain]}, got {domain!r}"
    )


def _coerce_band(band) -> StateBand:
    if isinstance(band, StateBand):
        return band
    if isinstance(band, str):
        try:
            return StateBand(band.strip())
        except ValueError:
            pass
    raise DimensionDefinitionError(
        f"band must be one of {[b.value for b in StateBand]}, got {band!r}"
    )


@dataclass(frozen=True)
class DimensionDefinition:
    """Package-declared meaning for ONE numeric dimension.

    For ``RELATIONSHIP`` the ``id`` is the dimension only (the runtime key is
    ``<subject>.<dimension>`` -- the subject is runtime data and never part of
    the definition, which keeps definitions portable across characters). For
    ``PSYCHOLOGY`` the ``id`` is the whole runtime key.
    """

    domain: StateDomain
    id: str
    label: str
    description: str
    #: Meaning for every band in :data:`REQUIRED_BANDS`.
    band_meanings: Mapping[StateBand, str]
    #: Optional, concise, package-specific behavioural guidance per band.
    band_guidance: Mapping[StateBand, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", _coerce_domain(self.domain))

        if not isinstance(self.id, str) or not _DIMENSION_ID_RE.match(self.id or ""):
            raise DimensionDefinitionError(
                f"dimension id must match [a-z0-9_]+ (no subject prefix), got {self.id!r}"
            )
        for name, value in (("label", self.label), ("description", self.description)):
            if not isinstance(value, str) or not value.strip():
                raise DimensionDefinitionError(f"{name} must be a non-empty string")

        meanings: Dict[StateBand, str] = {}
        for raw_band, raw_meaning in dict(self.band_meanings).items():
            band = _coerce_band(raw_band)
            if not isinstance(raw_meaning, str) or not raw_meaning.strip():
                raise DimensionDefinitionError(
                    f"meaning for band {band.value} must be a non-empty string"
                )
            meanings[band] = raw_meaning.strip()
        missing = [b.value for b in REQUIRED_BANDS if b not in meanings]
        if missing:
            raise DimensionDefinitionError(
                f"band_meanings is missing required band(s): {missing}"
            )
        extra = [b.value for b in meanings if b not in REQUIRED_BANDS]
        if extra:  # pragma: no cover - _coerce_band already constrains this
            raise DimensionDefinitionError(f"band_meanings has unknown band(s): {extra}")

        guidance: Dict[StateBand, str] = {}
        for raw_band, raw_text in dict(self.band_guidance or {}).items():
            band = _coerce_band(raw_band)
            if not isinstance(raw_text, str) or not raw_text.strip():
                raise DimensionDefinitionError(
                    f"guidance for band {band.value} must be a non-empty string"
                )
            guidance[band] = raw_text.strip()

        object.__setattr__(self, "band_meanings", MappingProxyType(meanings))
        object.__setattr__(self, "band_guidance", MappingProxyType(guidance))

    # -- accessors -------------------------------------------------------
    def meaning_for(self, band: StateBand) -> str:
        return self.band_meanings[_coerce_band(band)]

    def guidance_for(self, band: StateBand) -> Optional[str]:
        return self.band_guidance.get(_coerce_band(band))

    def band_meaning_records(self) -> Tuple[DimensionBandMeaning, ...]:
        return tuple(
            DimensionBandMeaning(band=b, meaning=self.band_meanings[b])
            for b in REQUIRED_BANDS
        )

    @classmethod
    def from_dict(cls, raw: Mapping) -> "DimensionDefinition":
        """Build (and validate) a definition from a loader-neutral mapping.

        Expected shape::

            {
              "domain": "RELATIONSHIP" | "PSYCHOLOGY",
              "id": "<dimension id>",
              "label": "...",
              "description": "...",
              "band_meanings": {"VERY_LOW": "...", ..., "VERY_HIGH": "..."},
              "band_guidance": {"HIGH": "..."}          # optional
            }
        """
        if not isinstance(raw, Mapping):
            raise DimensionDefinitionError("dimension definition must be a mapping")
        unknown = set(raw) - {
            "domain",
            "id",
            "label",
            "description",
            "band_meanings",
            "band_guidance",
        }
        if unknown:
            raise DimensionDefinitionError(
                f"unknown dimension definition field(s): {sorted(unknown)}"
            )
        for required in ("domain", "id", "label", "description", "band_meanings"):
            if required not in raw:
                raise DimensionDefinitionError(
                    f"dimension definition is missing required field {required!r}"
                )
        band_meanings = raw["band_meanings"]
        if not isinstance(band_meanings, Mapping):
            raise DimensionDefinitionError("band_meanings must be a mapping")
        band_guidance = raw.get("band_guidance") or {}
        if not isinstance(band_guidance, Mapping):
            raise DimensionDefinitionError("band_guidance must be a mapping")
        return cls(
            domain=raw["domain"],
            id=raw["id"],
            label=raw["label"],
            description=raw["description"],
            band_meanings=dict(band_meanings),
            band_guidance=dict(band_guidance),
        )


# --------------------------------------------------------------------------
# DimensionSet
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensionSet:
    """An immutable collection of definitions, unique per ``(domain, id)``.

    The next slice decides how a VERSIONED Character Package supplies these;
    this type is just the validated in-memory shape both a future loader and
    the current tests share.
    """

    definitions: Tuple[DimensionDefinition, ...] = ()

    def __post_init__(self) -> None:
        defs = tuple(self.definitions)
        for d in defs:
            if not isinstance(d, DimensionDefinition):
                raise DimensionDefinitionError(
                    "DimensionSet.definitions must contain DimensionDefinition instances"
                )
        seen = set()
        for d in defs:
            marker = (d.domain, d.id)
            if marker in seen:
                raise DimensionDefinitionError(
                    f"duplicate dimension definition for {d.domain.value}/{d.id}"
                )
            seen.add(marker)
        object.__setattr__(self, "definitions", defs)
        object.__setattr__(
            self, "_index", {(d.domain, d.id): d for d in defs}
        )

    def __iter__(self):
        return iter(self.definitions)

    def __len__(self) -> int:
        return len(self.definitions)

    def get(self, domain, dimension_id: str) -> Optional[DimensionDefinition]:
        try:
            key = (_coerce_domain(domain), dimension_id)
        except DimensionDefinitionError:
            return None
        return getattr(self, "_index", {}).get(key)

    @classmethod
    def from_dicts(cls, raw_defs: Sequence[Mapping]) -> "DimensionSet":
        """Validate a loader-neutral list of mappings into a DimensionSet."""
        if isinstance(raw_defs, Mapping) or not isinstance(raw_defs, (list, tuple)):
            raise DimensionDefinitionError(
                "dimension definitions must be a list/tuple of mappings"
            )
        return cls(tuple(DimensionDefinition.from_dict(d) for d in raw_defs))

    @classmethod
    def coerce(cls, value) -> Optional["DimensionSet"]:
        """Best-effort adapter: a DimensionSet passes through; a list/tuple of
        mappings is validated; ``None`` / empty yields ``None``. Anything else
        raises :class:`DimensionDefinitionError` (a misconfigured package
        should fail loudly, not be silently ignored)."""
        if value is None:
            return None
        if isinstance(value, DimensionSet):
            return value if len(value) else None
        if isinstance(value, (list, tuple)):
            if not value:
                return None
            return cls.from_dicts(value)
        raise DimensionDefinitionError(
            f"unsupported dimension-definitions value: {type(value).__name__}"
        )


# --------------------------------------------------------------------------
# Interpretation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class InterpretedDimensionState:
    """The semantic reading of one numeric dimension at one point in time."""

    domain: StateDomain
    dimension_id: str
    status: DimensionValueStatus
    runtime_key: Optional[str] = None
    subject: Optional[str] = None
    value: Optional[int] = None
    band: Optional[StateBand] = None
    meaning: Optional[str] = None
    guidance: Optional[str] = None


def band_for_value(value: int) -> StateBand:
    """Map an in-range integer to its generic band. Pure and total over
    ``[-100, 100]``; raises for a non-int, a bool, or an out-of-range value
    (never clamps)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DimensionDefinitionError(f"value must be an int, got {value!r}")
    if not (NUMERIC_STATE_MIN <= value <= NUMERIC_STATE_MAX):
        raise DimensionDefinitionError(
            f"value {value} out of range [{NUMERIC_STATE_MIN}, {NUMERIC_STATE_MAX}]"
        )
    for band, lo, hi in BAND_THRESHOLDS:
        if lo <= value <= hi:
            return band
    raise AssertionError("unreachable: bands cover the whole range")  # pragma: no cover


def interpret_value(
    value: Optional[int],
    definition: DimensionDefinition,
    *,
    runtime_key: Optional[str] = None,
    subject: Optional[str] = None,
) -> InterpretedDimensionState:
    """Interpret ``value`` against ``definition``.

    ``value is None`` -> a ``MISSING`` reading (no band, no meaning) -- it is
    never treated as ``0``. Otherwise the returned state carries the exact
    integer, its generic band, and the dimension-specific meaning/guidance
    taken verbatim from ``definition`` (Core never infers meaning from the
    dimension id).
    """
    if not isinstance(definition, DimensionDefinition):
        raise DimensionDefinitionError("definition must be a DimensionDefinition")

    if value is None:
        return InterpretedDimensionState(
            domain=definition.domain,
            dimension_id=definition.id,
            status=DimensionValueStatus.MISSING,
            runtime_key=runtime_key,
            subject=subject,
        )

    band = band_for_value(value)
    return InterpretedDimensionState(
        domain=definition.domain,
        dimension_id=definition.id,
        status=DimensionValueStatus.KNOWN,
        runtime_key=runtime_key,
        subject=subject,
        value=value,
        band=band,
        meaning=definition.meaning_for(band),
        guidance=definition.guidance_for(band),
    )


def key_to_dimension_id(domain, key: str) -> Tuple[str, Optional[str]]:
    """Split a runtime state key into ``(dimension_id, subject)``.

    - ``RELATIONSHIP``: ``"<subject>.<dimension>"`` -> ``(dimension, subject)``
    - ``PSYCHOLOGY``:   ``"<dimension>"``           -> ``(dimension, None)``

    Raises :class:`DimensionDefinitionError` if the key does not match the
    existing runtime grammar for that domain (this never loosens it).
    """
    dom = _coerce_domain(domain)
    key = (key or "").strip()
    if dom is StateDomain.RELATIONSHIP:
        if key.count(".") != 1:
            raise DimensionDefinitionError(
                f"RELATIONSHIP key must be <subject>.<dimension>, got {key!r}"
            )
        subject, dimension = key.split(".", 1)
        if not _DIMENSION_ID_RE.match(subject) or not _DIMENSION_ID_RE.match(dimension):
            raise DimensionDefinitionError(
                f"RELATIONSHIP key parts must match [a-z0-9_]+, got {key!r}"
            )
        return dimension, subject
    # PSYCHOLOGY
    if not _DIMENSION_ID_RE.match(key):
        raise DimensionDefinitionError(
            f"PSYCHOLOGY key must match [a-z0-9_]+, got {key!r}"
        )
    return key, None


def _coerce_state_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _CANONICAL_INT_RE.match(value.strip()):
        return int(value.strip())
    return None


def interpret_state_entry(
    domain,
    key: str,
    value,
    dimension_set: Optional[DimensionSet],
) -> Optional[InterpretedDimensionState]:
    """Resolve one current-state entry to a semantic reading, or ``None`` when
    it cannot be interpreted (no matching definition, unresolvable key, or a
    non-integer value) -- callers then fall back to the raw representation
    rather than inventing meaning.
    """
    if dimension_set is None:
        return None
    try:
        dom = _coerce_domain(domain)
    except DimensionDefinitionError:
        return None
    try:
        dimension_id, subject = key_to_dimension_id(dom, key)
    except DimensionDefinitionError:
        return None
    definition = dimension_set.get(dom, dimension_id)
    if definition is None:
        return None
    int_value = _coerce_state_int(value)
    if int_value is None:
        return None
    if not (NUMERIC_STATE_MIN <= int_value <= NUMERIC_STATE_MAX):
        return None
    return interpret_value(
        int_value, definition, runtime_key=str(key).strip(), subject=subject
    )


# --------------------------------------------------------------------------
# Provider-ready rendering
# --------------------------------------------------------------------------

#: Marker used when a key has no resolvable definition -- semantic meaning is
#: never fabricated from the id.
_UNRESOLVED_SUFFIX = " (semantics: not defined by package)"


def semantic_state_line(
    domain,
    key: str,
    value,
    dimension_set: Optional[DimensionSet],
    *,
    mark_unresolved: bool = False,
) -> str:
    """One compact provider-ready line.

    With a resolving definition::

        - <runtime key>: <value> (band: <BAND>) — <package-declared meaning>

    Without one, the existing raw representation is preserved verbatim
    (optionally flagged when ``mark_unresolved`` is set).
    """
    raw = f"- {str(key).strip()}: {str(value).strip()}"
    interp = interpret_state_entry(domain, key, value, dimension_set)
    if interp is None or interp.status is not DimensionValueStatus.KNOWN or interp.band is None:
        return raw + (_UNRESOLVED_SUFFIX if mark_unresolved else "")
    return f"{raw} (band: {interp.band.value}) — {interp.meaning}"


def render_semantic_state(
    entries: Iterable[Mapping],
    dimension_set: Optional[DimensionSet],
) -> str:
    """Render current numeric state entries (``{"domain","key","value"}``) as a
    compact block, grouped by domain in a deterministic order. FACT entries
    are ignored (not a numeric semantic domain)."""
    by_domain: Dict[StateDomain, list] = {d: [] for d in StateDomain}
    for entry in entries:
        raw_domain = (entry.get("domain") or "").strip() if isinstance(entry, Mapping) else ""
        try:
            dom = _coerce_domain(raw_domain)
        except DimensionDefinitionError:
            continue
        by_domain[dom].append(entry)

    lines: list = []
    for dom in StateDomain:
        rows = by_domain[dom]
        if not rows:
            continue
        lines.append(dom.value)
        for entry in rows:
            lines.append(
                semantic_state_line(
                    dom, entry.get("key", ""), entry.get("value", ""), dimension_set
                )
            )
    return "\n".join(lines)
