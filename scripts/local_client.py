"""Local synthetic HTTP helpers. Never print response bodies containing tokens."""
import json
import pathlib
import requests
ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:18069'

def fixtures():
    return json.loads((ROOT / 'runtime/accounts.json').read_text())

def session(key):
    a = fixtures()[key]
    client = requests.Session()
    result = client.post(BASE + '/web/session/authenticate', json={'jsonrpc': '2.0', 'id': 1, 'params': {'db': 'packaging_poc', 'login': a['login'], 'password': a['password']}}).json()
    assert result.get('result', {}).get('uid') == a['uid'], 'Local fixture authentication failed'
    return client

def rpc(client, path, params=None):
    return client.post(BASE + path, json={'jsonrpc': '2.0', 'id': 1, 'params': params or {}}).json()

def api(client, method, context=None, input=None):
    body = rpc(client, '/poc/api', {'method': method, 'context': context or {}, 'input': input or {}})
    assert 'error' not in body, 'Unexpected authenticated RPC failure'
    return body['result']
