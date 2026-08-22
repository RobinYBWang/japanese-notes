# add_datasay_clips.py — 補齊 HTML 裡所有 data-say 文本（文法例句、按鈕…）缺的 clip
#
# add_missing_clips.py 只掃單字資料（sayText/kana/動詞活用），
# 文法區塊 GRAMMAR_DEFAULT 裡的 <button data-say="…"> 不在它的涵蓋範圍。
# 這一支用正規表示式收 HTML 原始碼裡所有 data-say，補齊三個角色的音檔。
#
# 執行： python3 add_datasay_clips.py minna-notes.html
#
import json, re, os, sys, hashlib, base64, subprocess, urllib.parse, urllib.request

HTML = sys.argv[1] if len(sys.argv) > 1 else 'minna-notes.html'
VOICES = [2, 11, 13]
BASE = 'http://127.0.0.1:50021'
TMP = '/tmp/_dsclip'

h = open(HTML, encoding='utf-8').read()

mvv = re.search(r'<script[^>]*id="vv-data"[^>]*>(.*?)</script>', h, re.S)
if not mvv:
    sys.exit('找不到 <script id="vv-data">')
VV = json.loads(mvv.group(1))
say, audio = VV['say'], VV['audio']

STRIP = re.compile(r'[～~［］\[\]]')
norm = lambda t: STRIP.sub('', str(t or '')).replace('　', ' ').strip()
aid = lambda text, sp: hashlib.md5((str(sp) + '|' + text).encode()).hexdigest()[:12]

# 排除 JS 樣板片段：主程式裡有 data-say="'+esc(x)+'" 或 data-say="${q.say}" 這種
# 「還沒被求值」的字串，收進來會合成出一堆垃圾音檔（實際踩過，檔案胖了 0.6MB）。
CODEY = re.compile(r"\$\{|'\+|\+'|[<>\\]")
texts = sorted({norm(t) for t in re.findall(r'data-say="([^"]*)"', h)
                if norm(t) and not CODEY.search(t)})
todo = [(t, v, aid(t, v)) for t in texts for v in VOICES
        if not say.get(t, {}).get(str(v)) or say[t][str(v)] not in audio]
print('data-say 文本 %d 個；缺的 clip %d 個' % (len(texts), len(todo)))
if not todo:
    print('沒有缺的。'); sys.exit(0)
print('缺的文本：', sorted({t for t, _, _ in todo}))

os.makedirs(TMP, exist_ok=True)


def synth(text, sp):
    q = urllib.parse.urlencode({'text': text, 'speaker': sp})
    query = urllib.request.urlopen(
        urllib.request.Request(f'{BASE}/audio_query?{q}', method='POST'), timeout=60).read()
    wav = urllib.request.urlopen(
        urllib.request.Request(f'{BASE}/synthesis?speaker={sp}', data=query,
                               headers={'Content-Type': 'application/json'}, method='POST'),
        timeout=180).read()
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
out = h[:mvv.start(1)] + newvv + h[mvv.end(1):]
fd = os.open(HTML, os.O_WRONLY | os.O_TRUNC)
os.write(fd, out.encode('utf-8'))
os.fsync(fd)
os.close(fd)
sz = os.path.getsize(HTML) / 1e6
print('完成：新增 %d 個 clip，已寫回 %s（%.1fMB）' % (done, HTML, sz))
if sz >= 20:
    print('⚠ 檔案 >=20MB，device commit 會失敗，需考慮音檔外置')
