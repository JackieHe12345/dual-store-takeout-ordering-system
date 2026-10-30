"""Read-only post-deployment checks. Run inside the live backend container."""
import json
import os
import urllib.request
import urllib.error

BASE = 'http://nginx/'

def request(path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    return urllib.request.urlopen(req, timeout=15)

def get(path, token=None):
    with request(path, token=token) as response:
        return json.load(response)

entries = ['Adiandiancan','Bdiandiancan','Adianneibuguanli','Bdianneibuguanli','neibuguanli']
for entry in entries:
    with request(entry + '/') as response:
        assert response.status == 200
    assert get(entry + '/api/health')['database'] == 'ok'
    features = get(entry + '/api/commerce/capabilities')
    assert features['enabled'] is True and features['is_test'] is False
    assert features['payment_enabled'] is False
    print('PASS public entry and commerce capability:', entry)

store_ids = []
for entry in entries[:2]:
    menu = get(entry + '/api/menu')
    store_ids.append(menu['store']['id'])
    assert '测试' not in menu['store']['name']
    catalog = get(entry + '/api/commerce/catalog')
    assert catalog['is_test'] is False
    print('PASS store menu and catalog:', menu['store']['name'])
assert len(set(store_ids)) == 2

accounts = [('neibuguanli','admin','SEED_SUPER_ADMIN_PASSWORD',store_ids), ('Adianneibuguanli','staff_a','SEED_STORE_A_PASSWORD',[store_ids[0]]), ('Bdianneibuguanli','staff_b','SEED_STORE_B_PASSWORD',[store_ids[1]])]
for entry, username, env_key, ids in accounts:
    with request(entry + '/api/auth/login', {'username': username, 'password': os.environ[env_key]}) as response:
        token = json.load(response)['access_token']
    for sid in ids:
        assert isinstance(get(f'{entry}/api/commerce/manage/{sid}/members', token), list)
        stats = get(f'{entry}/api/commerce/manage/{sid}/stats', token)
        assert stats['is_test'] is False and stats['real_revenue_cents'] == 0
        assert all('unpaid_total_cents' in row for row in stats['by_status'])
    if username == 'staff_a':
        try:
            get(f'Bdianneibuguanli/api/commerce/manage/{store_ids[1]}/members', token)
            raise AssertionError('Cross-store request was unexpectedly accepted')
        except urllib.error.HTTPError as exc:
            assert exc.code == 403, exc.code
    print('PASS account and member management:', username)
print('LIVE_ACCEPTANCE_PASSED: original URLs, existing accounts, store isolation, commerce enabled, online payment disabled.')
