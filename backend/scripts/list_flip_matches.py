import sys
sys.path.insert(0, r'D:\git\astrosummary\backend')
from nina_session_analyzer import TS_RE, PAT
p = r'Q:\\syncthing\\data1\\NINA Logs\\20250903-182800-3.1.2.9001.3240-202509.log'
text = open(p,'r',encoding='utf-8').read()
lines = text.splitlines()
for i,ln in enumerate(lines):
    m = TS_RE.match(ln)
    if not m:
        continue
    ts = m.group('ts')
    msg = m.group('msg')
    matched = []
    for k in ('flip_start','flip_physical_start','flip_done_alt','flip_done'):
        try:
            if PAT[k].search(msg):
                matched.append(k)
        except KeyError:
            pass
    if matched:
        print(f"{i+1}: {ts} | {matched} | {msg}")
