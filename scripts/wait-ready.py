#!/usr/bin/env python3
import time, requests
for _ in range(45):
    try:
        r = requests.get('http://127.0.0.1:18069/web/login', timeout=2)
        if r.status_code == 200:
            print('Local Odoo HTTP ready')
            break
    except requests.RequestException:
        pass
    time.sleep(1)
else:
    raise SystemExit('Local Odoo not ready after 45 seconds')
