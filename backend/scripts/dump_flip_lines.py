import sys
sys.path.insert(0, r'D:\git\astrosummary\backend')
from nina_session_analyzer import TS_RE
p = r'Q:\\syncthing\\data1\\NINA Logs\\20250903-182800-3.1.2.9001.3240-202509.log'
text = open(p,'r',encoding='utf-8').read()
lines = text.splitlines()
for i,ln in enumerate(lines):
    lnl = ln.lower()
    if 'meridian' in lnl or 'recenter' in lnl or 'resuming autoguider' in lnl or 'passmeridian' in lnl or 'doflip' in lnl or 'pass meridian' in lnl:
        m = TS_RE.match(ln)
        if m:
            print(f"{i+1}: {m.group('ts')} | {m.group('msg')}")
