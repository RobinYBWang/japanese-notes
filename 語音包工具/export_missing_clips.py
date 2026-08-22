# export_missing_clips.py —— 【在雲端容器跑】只把「缺的音檔」匯出成一個小 JSON
#
# 為什麼要拆成 export / merge 兩段：
#   device_commit_files（雲端 → 使用者電腦）每個檔案上限 20MB，
#   而 minna-notes.html 已經 17.9MB，遲早過不去。
#   反方向的 device_stage_files（使用者電腦 → 雲端）上限是 400MB。
#   所以：大檔只往上走，往下走的只有這個幾百 KB 的 clip 包。
#   合併由 merge_clips.py 在使用者電腦上做，HTML 從頭到尾不離開他的硬碟。
#
# 文本來源涵蓋兩種（這支是 add_missing_clips.py + add_datasay_clips.py 的聯集）：
#   A. vocab-data：各課單字的 sayText（漢字優先／sayForceKana 強制假名）＋ kana ＋ 動詞活用形
#   B. HTML 原始碼裡所有 data-say：文法例句的 🔊 按鈕等
#   只跑 A 會漏掉文法例句的音檔（2026-08-22 踩過）。
#
# 前置：VOICEVOX engine 已在 127.0.0.1:50021 跑起來；ffmpeg 可用。
# 執行：python3 export_missing_clips.py minna-notes.html new-clips.json
#
import json, re, os, sys, hashlib, base64, subprocess, tempfile, urllib.parse, urllib.request

HTML = sys.argv[1] if len(sys.argv) > 1 else 'minna-notes.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'new-clips.json'
VOICES = [2, 11, 13]          # 2=四国めたん(聲音A) / 11=玄野武宏(聲音B) / 13=青山龍星
VERB_SUFS = ['ます', 'ません', 'ました', 'ませんでした']
SAY_FORCE_KANA = {'水餃', '車', '何', '薬', '家', '百', '千', '101', '眼鏡', '梅酒', '夜市',
                  '元', '何階', '木', '鈴', '時', '分', '今', '昼', '明日'}
BASE = 'http://127.0.0.1:50021'
TMP = os.path.join(tempfile.gettempdir(), '_exportclip')   # Windows 上 /tmp 不存在

# 主程式裡有 data-say="'+esc(x)+'"、data-say="${q.say}" 這種還沒求值的 JS 樣板字串，
# 收進來會合成出一堆垃圾音檔（2026-08-22 實際踩到，檔案胖了 0.6MB）。不要拿掉這個過濾。
CODEY = re.compile(r"\$\{|'\+|\+'|[<>\\]")

STRIP = re.compile(r'[～~［］\[\]]')
norm = lambda t: STRIP.sub('', str(t or '')).replace('　', ' ').strip()
aid = lambda text, sp: hashlib.md5((str(sp) + '|' + text).encode()).hexdigest()[:12]

h = open(HTML, encoding='utf-8').read()


def block(idv, required=True):
    m = re.search(r'<script[^>]*id="' + idv + r'"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        if required:
            sys.exit('找不到 <script id="%s">' % idv)
        return None
    return json.loads(m.group(1))


# 這支同時吃兩種頁面：minna-notes（vocab-data）與 kana.html（kana-data）。
vd = block('vocab-data', required=False)
kana = block('kana-data', required=False)
if vd is None and kana is None:
    sys.exit('這個 HTML 既沒有 vocab-data 也沒有 kana-data，不知道要合成什麼')
VV = block('vv-data')
say, audio = VV['say'], VV['audio']


def say_text(r):  # port 自前端 sayText()
    w = STRIP.sub('', (r.get('word') or '')).strip()
    if w and w not in SAY_FORCE_KANA:
        return w
    return re.sub(r'\s*\n\s*', '、', (r.get('kana') or '').replace('～', '').replace('~', '')).strip()


texts = set()


def add(t):
    t = norm(t)
    if t:
        texts.add(t)


# A. 單字（minna-notes）／假名與例詞（kana.html）
if vd:
    for k, rows in vd['lessons'].items():   # 第0課已於 2026-08-22 獨立成 kana.html
        for r in rows:
            add(say_text(r))
            add(r.get('kana'))
            ka = r.get('kana') or ''
            if ka.endswith('ます') and 2 < len(ka) <= 9:   # 動詞活用形（排除長片語）
                stem = ka[:-2]
                for s in VERB_SUFS:
                    add(stem + s)
if kana:
    for r in kana:
        add(r.get('hira'))
        add(r.get('kata'))
        for f in ('hiraex', 'kataex'):     # 例詞要去掉「（中文）」
            add((r.get(f) or '').split('（')[0])

# B. data-say
for t in re.findall(r'data-say="([^"]*)"', h):
    if not CODEY.search(t):
        add(t)

todo = [(t, v, aid(t, v)) for t in sorted(texts) for v in VOICES
        if not say.get(t, {}).get(str(v)) or say[t][str(v)] not in audio]
print('文本 %d 個；缺的 clip %d 個' % (len(texts), len(todo)))
if not todo:
    json.dump({'say': {}, 'audio': {}}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('沒有缺的，已寫出空的 %s。' % OUT)
    sys.exit(0)
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
    if len(b) < 300 * 4 // 3:      # 完整性閾值：單一假名的 opus 可能小於 500B
        raise RuntimeError('clip too small: ' + text)
    return b


new_say, new_audio = {}, {}
for i, (t, v, cid) in enumerate(todo, 1):
    new_audio[cid] = synth(t, v)
    new_say.setdefault(t, {})[str(v)] = cid
    if i % 10 == 0 or i == len(todo):
        print('  ...%d/%d' % (i, len(todo)))

json.dump({'say': new_say, 'audio': new_audio}, open(OUT, 'w', encoding='utf-8'),
          ensure_ascii=False)
sz = os.path.getsize(OUT) / 1e6
print('完成：%d 個 clip / %d 個文本 → %s（%.2fMB）' % (len(new_audio), len(new_say), OUT, sz))
if sz >= 19:
    print('⚠ clip 包 >=19MB，device_commit_files 會拒絕，分批匯出')
print('接下來在使用者電腦上跑：python3 merge_clips.py <minna-notes.html> %s' % OUT)
