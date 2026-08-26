#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Production Media Asset Binding v0.

All errors describe fail-closed validation/resolution of an explicit
media-item -> production-asset binding. No provider, LLM, media, or
filesystem semantics are involved in the binding itself.
"""

from __future__ import annotations


class ProductionMediaAssetBindingError(Exception):
    """Root of the Production Media Asset Binding exception hierarchy."""


class BindingValidationError(ProductionMediaAssetBindingError):
    """Raised when a binding input fails fail-closed validation."""


class AssetResolutionError(ProductionMediaAssetBindingError):
    """Raised when a binding cannot be resolved through Registry records."""


class AssetNotFoundError(AssetResolutionError):
    """Raised when the binding's asset_id matches no Registry record."""


class AssetIdAmbiguousError(AssetResolutionError):
    """Raised when the binding's asset_id matches multiple Registry records."""