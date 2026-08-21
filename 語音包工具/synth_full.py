# 批次合成 manifest 中的所有 utterance → mp3(32k mono),含失敗重試與完整性檢查
import json, subprocess, urllib.parse, urllib.request, os, sys
from concurrent.futures import ThreadPoolExecutor

BASE = 'http://127.0.0.1:50021'
M = json.load(open('/home/claude/full/manifest_full.json', encoding='utf-8'))
OUT = '/home/claude/full/audio'
os.makedirs(OUT, exist_ok=True)

def synth(item):
    k, u = item
    mp3 = f'{OUT}/{k}.mp3'
    if os.path.exists(mp3) and os.path.getsize(mp3) > 500:
        return (k, 'cached')
    for attempt in range(3):
        try:
            q = urllib.parse.urlencode({'text': u['text'], 'speaker': u['speaker']})
            req = urllib.request.Request(f'{BASE}/audio_query?{q}', method='POST')
            query = urllib.request.urlopen(req, timeout=60).read()
            req2 = urllib.request.Request(f'{BASE}/synthesis?speaker={u["speaker"]}',
                                          data=query, headers={'Content-Type': 'application/json'}, method='POST')
            wav = urllib.request.urlopen(req2, timeout=120).read()
            wavf = f'{OUT}/{k}.wav'
            open(wavf, 'wb').write(wav)
            r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wavf,
                                '-ac', '1', '-b:a', '32k', mp3], capture_output=True)
            os.remove(wavf)
            if r.returncode == 0 and os.path.getsize(mp3) > 500:
                return (k, 'ok')
        except Exception as e:
            err = str(e)
    return (k, 'FAIL')

items = list(M['utter'].items())
with ThreadPoolExecutor(max_workers=2) as ex:
    results = list(ex.map(synth, items))
fails = [k for k, s in results if s == 'FAIL']
total = sum(os.path.getsize(f'{OUT}/{k}.mp3') for k, s in results if s != 'FAIL')
print(f'done {len(results) - len(fails)}/{len(results)}  total {total/1e6:.1f}MB')
if fails:
    print('FAILED ids:', fails); sys.exit(1)
