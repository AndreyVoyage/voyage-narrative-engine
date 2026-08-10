#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 4 bounded pilot CLI.

Pilot-only argparse interface for:

  load-snapshot  -- load and validate the frozen pilot source snapshot
  run-probe      -- execute one probe mode (synthetic fixtures only)
  assemble-result -- assemble a result package from a prior run
  inspect        -- inspect a stored result package

Never performs network calls, real provider selection, or canon mutation.
Run with ``--help`` for sub-command usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# Ensure the repo root is on sys.path so absolute imports work
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _add_storage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-path",
        default="local_runs/cis_pilot",
        help="Storage base directory (default: local_runs/cis_pilot)",
    )


def _load_snapshot(base_path: str) -> None:
    from tools.cis_pilot.source_loader import load_pilot_source_snapshot
    from tools.cis_pilot.result_package import collect_source_artifacts

    snapshot = load_pilot_source_snapshot()
    artifacts = collect_source_artifacts(snapshot)
    print(f"Snapshot loaded: HEAD={snapshot.repo_head_sha}")
    print(f"P3 trust={snapshot.p3.trust}, attraction={snapshot.p3.attraction}")
    print(f"P4 strategies: {len(snapshot.p4_strategy_map)}")
    print(f"Source artifacts: {len(artifacts)}")
    for a in artifacts:
        print(f"  {a.repo_relative_path}  {a.sha256[:16]}...")


def _run_probe(mode: str, sub_mode: Optional[str], base_path: str, samples: int) -> None:
    if mode not in ("PB-REC", "PB-MEM", "PB-AB", "PB-LEAK"):
        print(f"ERROR: unsupported probe mode: {mode!r}", file=sys.stderr)
        sys.exit(1)

    from tools.cis_pilot.storage import CisPilotStorage
    from tools.cis_pilot.probe_runner import (
        ProbeRunner,
        ProbeRunConfig,
        ProbeDefinition,
        SYNTHETIC_PROBES,
        default_boundary,
    )
    from tools.cis_pilot.provider_boundary import SUPPORTED_PROVIDER
    from tools.cis_pilot.source_loader import load_pilot_source_snapshot
    from tools.cis_pilot.result_package import persist_result_package, generate_run_id

    storage = CisPilotStorage(base_path)
    snapshot = load_pilot_source_snapshot()
    runner = ProbeRunner(snapshot, storage)

    # Find the matching synthetic probe
    probe = None
    for p in SYNTHETIC_PROBES:
        if p.mode == mode:
            probe = p
            break

    if probe is None:
        print(f"ERROR: no synthetic probe for mode {mode!r}", file=sys.stderr)
        sys.exit(1)

    boundary = default_boundary()
    config = ProbeRunConfig(probe=probe, boundary=boundary, samples_per_arm=samples)

    print(f"Running {mode}" + (f"/{sub_mode}" if sub_mode else ""))
    print(f"  Provider: {SUPPORTED_PROVIDER}")
    print(f"  Samples per arm: {samples}")

    if mode == "PB-MEM":
        package = runner.run_pb_mem(config)
    elif mode == "PB-REC":
        package = runner.run_pb_rec(config)
    elif mode == "PB-AB":
        if sub_mode is None:
            sub_mode = "T3-P3"
        package = runner.run_pb_ab(config, sub_mode=sub_mode)
    elif mode == "PB-LEAK":
        package = runner.run_pb_leak(config)

    paths = persist_result_package(storage, package)
    print(f"\nResult package saved (run_id={package.run_id}):")
    for name, rel_path in sorted(paths.items()):
        print(f"  {name}: {rel_path}")


def _assemble_result(run_id: str, base_path: str) -> None:
    from tools.cis_pilot.storage import CisPilotStorage
    from tools.cis_pilot.result_package import ResultPackage

    storage = CisPilotStorage(base_path)
    path = f"results/{run_id}/result_package.json"
    if not storage.exists(path):
        print(f"ERROR: result package not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = storage.read_json(path)
    print(f"Run: {data.get('run_id', '?')}")
    print(f"Mode: {data.get('mode', '?')}")
    print(f"Sub-mode: {data.get('sub_mode')}")
    print(f"Samples: {len(data.get('samples', []))}")
    dc = data.get("deterministic_checks", {})
    for k, v in sorted(dc.items()):
        print(f"  {k}: {v}")


def _inspect(base_path: str) -> None:
    from tools.cis_pilot.storage import CisPilotStorage
    from pathlib import Path as _Path

    storage = CisPilotStorage(base_path)
    results_dir = _Path(base_path) / "results"
    if not results_dir.is_dir():
        print("No results directory found.")
        return

    run_ids = sorted(d.name for d in results_dir.iterdir() if d.is_dir())
    if not run_ids:
        print("No result packages found.")
        return

    print(f"Found {len(run_ids)} result package(s):")
    for rid in run_ids:
        pkg_path = f"results/{rid}/result_package.json"
        try:
            data = storage.read_json(pkg_path)
            print(f"  {rid}: mode={data.get('mode','?')} sub={data.get('sub_mode','?')} samples={len(data.get('samples',[]))}")
        except Exception as exc:
            print(f"  {rid}: ERROR reading: {exc}")


def _main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cis-pilot",
        description="CIS Kira Pilot S4 CLI -- synthetic probe execution (mock-only, offline)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # load-snapshot
    p_load = sub.add_parser("load-snapshot", help="Load and validate the frozen pilot source snapshot")
    _add_storage_args(p_load)

    # run-probe
    p_run = sub.add_parser("run-probe", help="Execute one synthetic probe mode")
    p_run.add_argument("--mode", required=True, choices=["PB-REC", "PB-MEM", "PB-AB", "PB-LEAK"])
    p_run.add_argument("--sub-mode", choices=["T3-P3", "T3-P4", "COMBINED"], default=None)
    p_run.add_argument("--samples", type=int, default=10, help="Samples per arm (default: 10)")
    _add_storage_args(p_run)

    # assemble-result
    p_asm = sub.add_parser("assemble-result", help="Inspect a stored result package")
    p_asm.add_argument("--run-id", required=True)
    _add_storage_args(p_asm)

    # inspect
    p_insp = sub.add_parser("inspect", help="List all stored result packages")
    _add_storage_args(p_insp)

    args = parser.parse_args(argv)

    if args.command == "load-snapshot":
        _load_snapshot(args.base_path)
    elif args.command == "run-probe":
        _run_probe(args.mode, args.sub_mode, args.base_path, args.samples)
    elif args.command == "assemble-result":
        _assemble_result(args.run_id, args.base_path)
    elif args.command == "inspect":
        _inspect(args.base_path)


if __name__ == "__main__":
    _main()