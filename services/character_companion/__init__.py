#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Companion -- the end-user chat client's backend surface.

Separate from Character Lab (the developer/operator/debug client). Composes the
same Character Runtime / Core lower layers through a minimal five-operation
service and a JSON transport; adds a durable COMPANION session registry and
reuses the existing Runtime Memory event log as conversation history.
"""

from .catalog import (
    CompanionCatalog,
    CompanionCharacterEntry,
    build_default_catalog,
)
from .service import (
    PURPOSE_COMPANION,
    CompanionError,
    CompanionMessage,
    CompanionProviderError,
    CompanionService,
    CompanionSession,
    CompanionTurn,
)
from .transport import CompanionTransport, CompanionTransportError

__all__ = [
    "CompanionCatalog",
    "CompanionCharacterEntry",
    "build_default_catalog",
    "PURPOSE_COMPANION",
    "CompanionError",
    "CompanionProviderError",
    "CompanionMessage",
    "CompanionService",
    "CompanionSession",
    "CompanionTurn",
    "CompanionTransport",
    "CompanionTransportError",
]
