"""Operator flow across HTTP, adapter and durable state; provider forbidden."""
import json
from pathlib import Path
import urllib.error
import urllib.request

import pytest

import character_lab_react_server as server_mod
from services.character_lab.app import CharacterLabApp
from services.character_lab.react_transport import ReactTransport, ReactTransportError
from services.character_lab.service_adapter import CharacterLabServiceAdapter
from services.character_runtime.state import RuntimeStateBackend


def forbidden_provider(*args, **kwargs):
    raise AssertionError('evolution operator flow must never call a provider')


def transport(root):
    app = CharacterLabApp(
        acceptance_root=Path(__file__).resolve().parents[2] / 'accepted',
        data_root=root, provider_factory=forbidden_provider,
        provider_info={'provider_id': 'forbidden', 'model': 'none'},
        provider_availability='UNCONFIGURED')
    return ReactTransport(CharacterLabServiceAdapter(app))


def proposal(workspace_id, **overrides):
    body = dict(workspaceId=workspace_id, domain='RELATIONSHIP', key='andrey.trust',
                operation='SET', proposedValue=20, reason='operator proposal',
                basisEventIds=['event-explicit-1'], confidence=1, timescale='SLOW')
    body.update(overrides)
    return body


def http(server, path, body=None):
    request = urllib.request.Request(server.base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def test_http_create_list_approve_reject_restart_and_workspace_isolation(tmp_path):
    t = transport(tmp_path)
    a = t.create_test_workspace()['workspaceId']
    b = t.create_test_workspace()['workspaceId']
    server = server_mod.ReactCharacterLabServer(t, port=0)
    server.start()
    try:
        status, c = http(server, '/api/evolution/candidates', proposal(a))
        assert status == 200 and c['status'] == 'PENDING'
        assert c['basis_event_ids'] == ['event-explicit-1']
        assert c['decision'] is None and c['state_event_id'] is None
        assert http(server, f'/api/workspaces/{a}/runtime-state')[1]['current'] == []
        decision = dict(workspaceId=b, candidateId=c['candidate_id'],
                        decision='APPROVE', decidedBy='operator', reason='verified')
        assert http(server, '/api/evolution/candidates/decision', decision)[0] == 404
        decision['workspaceId'] = a
        status, approved = http(server, '/api/evolution/candidates/decision', decision)
        assert status == 200 and approved['status'] == 'APPROVED'
        assert approved['decision']['decided_by'] == 'operator'
        assert approved['state_event_id']
        assert http(server, '/api/evolution/candidates/decision', decision)[0] == 409
        decision['decision'] = 'REJECT'
        assert http(server, '/api/evolution/candidates/decision', decision)[0] == 409
        _, rejected = http(server, '/api/evolution/candidates', proposal(a, timescale='AUTHOR_ONLY'))
        decision['candidateId'] = rejected['candidate_id']
        assert http(server, '/api/evolution/candidates/decision', decision)[1]['status'] == 'REJECTED'
        status, rows = http(server, f'/api/workspaces/{a}/evolution/candidates')
        assert status == 200
        assert {r['status'] for r in rows['candidates']} == {'APPROVED', 'REJECTED'}
        assert http(server, f'/api/workspaces/{b}/evolution/candidates')[1]['candidates'] == []
        assert http(server, f'/api/workspaces/{b}/runtime-state')[1]['current'] == []
    finally:
        server.shutdown()
    # Reconstruct the entire Lab and HTTP server from the same on-disk root.
    server = server_mod.ReactCharacterLabServer(transport(tmp_path), port=0)
    server.start()
    try:
        reloaded = http(server, f'/api/workspaces/{a}/evolution/candidates')[1]
        assert reloaded == rows
        state = http(server, f'/api/workspaces/{a}/runtime-state')[1]
        assert state['current'][0]['valueInt'] == 20
        assert state['current'][0]['sourceRef'] == f"evolution-candidate:{c['candidate_id']}"
    finally:
        server.shutdown()
    backend = RuntimeStateBackend(tmp_path / 'workspaces' / 'tests' / a, 'kira')
    assert len(backend.load_events('kira')) == 1
    backend.close()


@pytest.mark.parametrize('invalid', [
    {'domain': 'FACT'}, {'key': []}, {'basisEventIds': 'event-1'},
    {'basisEventIds': []}, {'basisEventIds': ['x', 'x']},
    {'confidence': True}, {'confidence': 2}, {'operation': 'REMOVE'},
    {'timescale': 'AUTO'}, {'reason': ' '}, {'proposedValue': 101},
    {'proposedValue': 2.5}, {'proposedDelta': 2}, {'subjectId': 'other'},
    {'status': 'APPROVED'}, {'path': '../elsewhere'},
])
def test_transport_malformed_candidate_no_persistence(tmp_path, invalid):
    t = transport(tmp_path)
    ws = t.create_test_workspace()['workspaceId']
    with pytest.raises(ReactTransportError) as exc:
        t.create_evolution_candidate(proposal(ws, **invalid))
    assert exc.value.status == 400
    assert t.list_evolution_candidates(ws)['candidates'] == ()
    assert t.get_runtime_state(ws)['current'] == []


@pytest.mark.parametrize('invalid', [
    {'decidedBy': ''}, {'decidedBy': True}, {'reason': []},
    {'decision': 'AUTO'}, {'proposedValue': 40},
])
def test_invalid_decision_stays_pending(tmp_path, invalid):
    t = transport(tmp_path)
    ws = t.create_test_workspace()['workspaceId']
    c = t.create_evolution_candidate(proposal(ws))
    body = dict(workspaceId=ws, candidateId=c['candidate_id'],
                decision='APPROVE', decidedBy='operator')
    body.update(invalid)
    with pytest.raises(ReactTransportError) as exc:
        t.decide_evolution_candidate(body)
    assert exc.value.status == 400
    assert t.list_evolution_candidates(ws)['candidates'][0]['status'] == 'PENDING'
    assert t.get_runtime_state(ws)['current'] == []


def test_http_adjust_conflict_remains_pending(tmp_path):
    t = transport(tmp_path)
    ws = t.create_test_workspace()['workspaceId']
    c = t.create_evolution_candidate(proposal(ws, operation='ADJUST', proposedValue=None, proposedDelta=10))
    body = dict(workspaceId=ws, candidateId=c['candidate_id'], decision='APPROVE', decidedBy='operator')
    server = server_mod.ReactCharacterLabServer(t, port=0)
    server.start()
    try:
        status, error = http(server, '/api/evolution/candidates/decision', body)
        assert status == 409 and error['error']['code'] == 'evolution_state_conflict'
        assert http(server, f'/api/workspaces/{ws}/evolution/candidates')[1]['candidates'][0]['status'] == 'PENDING'
        t.set_runtime_state(dict(workspaceId=ws, domain='RELATIONSHIP', key='andrey.trust', value='25'))
        assert http(server, '/api/evolution/candidates/decision', body)[0] == 200
        assert http(server, f'/api/workspaces/{ws}/runtime-state')[1]['current'][0]['valueInt'] == 35
    finally:
        server.shutdown()
