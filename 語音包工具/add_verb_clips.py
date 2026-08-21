# add_verb_clips.py — 只補「動詞小考活用形」缺的音檔，一鍵完成
#
# 用途：動詞小考播 vbRow.kana（各課 ます動詞 × ます/ません/ました/ませんでした）。
#       ます形本身是單字、已有錄音；ません/ました/ませんでした 常常沒錄 → 退回瀏覽器 TTS。
#       這支腳本只補那些缺的，直接改寫母版 HTML 的 <script id="vv-data">。
#
# 前置（要在「能跑 VOICEVOX 的環境」執行，例如 Claude Code 雲端容器）：
#   1) VOICEVOX engine 已在 127.0.0.1:50021 跑起來（見 README「VOICEVOX engine 安裝」）
#   2) ffmpeg 可用（opus 編碼）
#   3) 先把舊快取抽回也可以（非必須，本腳本只合成缺的）
#
# 執行：  python3 add_verb_clips.py /path/to/minna-notes.html
#
import json, re, os, sys, hashlib, base64, subprocess, urllib.parse, urllib.request

HTML = sys.argv[1] if len(sys.argv) > 1 else 'minna-notes.html'
VOICES = [2, 11, 13]          # 2=四国めたん(聲音A)；小考只用 A，但三個都補比較一致
SUFS = ['ます', 'ません', 'ました', 'ませんでした']
BASE = 'http://127.0.0.1:50021'
TMP = '/tmp/_verbclip'

h = open(HTML, encoding='utf-8').read()

def script_span(idv):
    m = re.search(r'<script[^>]*id="' + idv + r'"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        sys.exit('找不到 <script id="%s">' % idv)
    return m

mvoc = script_span('vocab-data'); vd = json.loads(mvoc.group(1))
mvv = script_span('vv-data'); VV = json.loads(mvv.group(1))
say, audio = VV['say'], VV['audio']

STRIP = re.compile(r'[～~［］\[\]]')
norm = lambda t: STRIP.sub('', str(t or '')).replace('　', ' ').strip()
aid = lambda text, sp: hashlib.md5((str(sp) + '|' + text).encode()).hexdigest()[:12]

# 1) 從單字資料算出所有動詞活用形（與母版 vbPool 同一過濾：ます結尾、長度<=9）
forms = set()
for k, rows in vd['lessons'].items():
    if k in ('0', '13', '14'):
        continue
    for r in rows:
        ka = r.get('kana') or ''
        if ka.endswith('ます') and 2 < len(ka) <= 9:
            stem = ka[:-2]
            for s in SUFS:
                forms.add(norm(stem + s))

# 2) 找出缺的 (text, voice)
todo = []
for t in sorted(forms):
    for v in VOICES:
        cid = say.get(t, {}).get(str(v))
        if not cid or cid not in audio:
            todo.append((t, v, aid(t, v)))
print('動詞活用形總數 %d；缺的 clip %d 個' % (len(forms), len(todo)))
if not todo:
    print('沒有缺的，不用做。'); sys.exit(0)

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
    if len(b) < 300 * 4 // 3:   # 完整性閾值 ~300 bytes
        raise RuntimeError('clip too small: ' + text)
    return b

done = 0
for t, v, cid in todo:
    b64 = synth(t, v)
    audio[cid] = b64
    say.setdefault(t, {})[str(v)] = cid
    done += 1
    print('  ok', t, 'voice', v)

# 3) 寫回 vv-data（只換那一段 JSON，其餘不動）
newvv = json.dumps(VV, ensure_ascii=False)
h2 = h[:mvv.start(1)] + newvv + h[mvv.end(1):]
open(HTML, 'w', encoding='utf-8').write(h2)
print('完成：新增 %d 個 clip，已寫回 %s' % (done, HTML))
