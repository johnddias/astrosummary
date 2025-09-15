from nina_session_analyzer import parse_nina_log
import json
p = r'Q:\\syncthing\\data1\\NINA Logs\\20250903-182800-3.1.2.9001.3240-202509.log'
text = open(p,'r',encoding='utf-8').read()
res = parse_nina_log(text)
print(json.dumps({
    'totals_seconds': res['totals_seconds'],
    'meridian_flips': [s for s in res['segments'] if s['label']=='meridian_flip'],
    'lines_total': res['lines_total'],
    'lines_matched': res['lines_matched'],
    'lines_skipped_ts': res['lines_skipped_ts']
}, indent=2))
