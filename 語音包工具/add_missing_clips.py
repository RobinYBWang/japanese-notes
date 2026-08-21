# add_missing_clips.py — 補齊所有「缺音檔」的單字＋動詞活用形，一鍵完成
#
# 用途：每次在本機 session 補了新單字（沒有錄音、只能 TTS）後，
#       在**能跑 VOICEVOX 的雲端 session**跑這一支，把所有缺的 clip 補齊。
#       涵蓋：各課單字的 sayText（漢字優先/強制假名）＋ kana ＋ 動詞活用形。
#       這支是 add_verb_clips.py 的超集（動詞活用形也含）。
#
# 前置（雲端 session）：VOICEVOX engine 已在 127.0.0.1:50021 跑起來；ffmpeg 可用。
# 執行：  python3 add_missing_clips.py "/path/to/japanese-notes/minna-notes.html"
#
import json, re, os, sys, hashlib, base64, subprocess, urllib.parse, urllib.request

HTML = sys.argv[1] if len(sys.argv) > 1 else 'minna-notes.html'
VOICES = [2, 11, 13]          # 2=四国めたん(聲音A，小考/單字預設用A)、11、13
VERB_SUFS = ['ます', 'ません', 'ました', 'ませんでした']
SAY_FORCE_KANA = {'車','何','薬','家','百','千','101','眼鏡','梅酒','夜市','元','何階','木','鈴','時','分','今','昼','明日'}
BASE = 'http://127.0.0.1:50021'
TMP = '/tmp/_missingclip'

h = open(HTML, encoding='utf-8').read()

def span(idv):
    m = re.search(r'<script[^>]*id="' + idv + r'"[^>]*>(.*?)</script>', h, re.S)
    if not m: sys.exit('找不到 <script id="%s">' % idv)
    return m

mvoc = span('vocab-data'); vd = json.loads(mvoc.group(1))
mvv = span('vv-data'); VV = json.loads(mvv.group(1))
say, audio = VV['say'], VV['audio']

STRIP = re.compile(r'[～~［］\[\]]')
norm = lambda t: STRIP.sub('', str(t or '')).replace('　', ' ').strip()
aid = lambda text, sp: hashlib.md5((str(sp) + '|' + text).encode()).hexdigest()[:12]

def say_text(r):  # port 自母版 sayText
    w = STRIP.sub('', (r.get('word') or '')).strip()
    if w and w not in SAY_FORCE_KANA: return w
    return re.sub(r'\s*\n\s*', '、', (r.get('kana') or '').replace('～', '').replace('~', '')).strip()

# 收集所有「單一詞句」文本：單字 sayText + kana，加動詞活用形
texts = set()
def add(t):
    t = norm(t)
    if t: texts.add(t)

for k, rows in vd['lessons'].items():
    if k == '0':      # 五十音例詞由完整管線處理，這裡略過
        continue
    for r in rows:
        add(say_text(r)); add(r.get('kana'))
        ka = r.get('kana') or ''
        if ka.endswith('ます') and 2 < len(ka) <= 9:   # 動詞活用形（排除長片語）
            stem = ka[:-2]
            for s in VERB_SUFS: add(stem + s)

# 找缺的 (text, voice)
todo = []
for t in sorted(texts):
    for v in VOICES:
        cid = say.get(t, {}).get(str(v))
        if not cid or cid not in audio:
            todo.append((t, v, aid(t, v)))
print('文本 %d 個；缺的 clip %d 個' % (len(texts), len(todo)))
if not todo:
    print('沒有缺的，全部已有音檔。'); sys.exit(0)

os.makedirs(TMP, exist_ok=True)

def synth(text, sp):
    q = urllib.parse.urlencode({'text': text, 'speaker': sp})
    query = urllib.request.urlopen(
        urllib.request.Request(f'{BASE}/audio_query?{q}', method='POST'), timeout=60).read()
    wav = urllib.request.urlopen(
        urllib.request.Request(f'{BASE}/synthesis?speaker={sp}', data=query,
                               headers={'Content-Type': 'application/json'}, method='POST'),
        timeout=120).read()
    wavf, oggf = f'{TMP}/c.wav', f'{TMP}/c.ogg'
    open(wavf, 'wb').write(wav)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wavf,
                    '-c:a', 'libopus', '-b:a', '16k', '-ac', '1', oggf], check=True)
    b = base64.b64encode(open(oggf, 'rb').read()).decode()
    if len(b) < 300 * 4 // 3:
        raise RuntimeError('clip too small: ' + text)
    return b

done = 0
for t, v, cid in todo:
    audio[cid] = synth(t, v)
    say.setdefault(t, {})[str(v)] = cid
    done += 1
    if done % 10 == 0 or done == len(todo):
        print('  ...%d/%d' % (done, len(todo)))

newvv = json.dumps(VV, ensure_ascii=False)
h2 = h[:mvv.start(1)] + newvv + h[mvv.end(1):]
open(HTML, 'w', encoding='utf-8').write(h2)
sz = os.path.getsize(HTML) / 1e6
print('完成：新增 %d 個 clip，已寫回 %s（%.1fMB）' % (done, HTML, sz))
if sz >= 20:
    print('⚠ 檔案 >=20MB，device commit 會失敗，需考慮音檔外置')
