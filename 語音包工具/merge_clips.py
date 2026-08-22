# merge_clips.py —— 【在使用者電腦上跑（device_bash）】把 clip 包併進 minna-notes.html
#
# 搭配 export_missing_clips.py（雲端）使用。大檔留在使用者硬碟上，只有 clip 包過橋。
# 實測：解析 17.9MB 的 HTML 約 0.4 秒，整支跑完遠在 device_bash 的 45 秒上限內。
#
# 執行：python3 merge_clips.py minna-notes.html new-clips.json
#
# 特性：
#   - 冪等：同一個 clip 包重複跑不會出事，已存在的直接跳過。
#   - 只動 <script id="vv-data">，其他一個字元都不碰。
#     ⚠ 特別是 <script id="vocab-data">：它是 indent=2 的縮排 JSON，
#       被壓成一行會讓 git diff 變成「-4556 +3」完全無法 review（2026-08-22 踩過）。
#       這支用切片的方式繞過整份重寫，所以不會動到它。
#   - vv-data 本身則本來就是壓縮成一行的，維持原樣。
#
import json, re, os, sys

HTML = sys.argv[1] if len(sys.argv) > 1 else 'minna-notes.html'
PACK = sys.argv[2] if len(sys.argv) > 2 else 'new-clips.json'

h = open(HTML, encoding='utf-8').read()
pack = json.load(open(PACK, encoding='utf-8'))
p_say, p_audio = pack.get('say', {}), pack.get('audio', {})

if not p_audio:
    print('clip 包是空的，沒事可做。')
    sys.exit(0)

m = re.search(r'(<script[^>]*id="vv-data"[^>]*>)(.*?)(</script>)', h, re.S)
if not m:
    sys.exit('找不到 <script id="vv-data">')
VV = json.loads(m.group(2))
say, audio = VV['say'], VV['audio']

before_a, before_s = len(audio), len(say)

# 先確認 clip 包自身完整：每個 say 指到的 id 都要有音檔
dangling = [(t, v, cid) for t, d in p_say.items() for v, cid in d.items() if cid not in p_audio]
if dangling:
    sys.exit('clip 包壞了，這些文本指到不存在的音檔：%s' % dangling[:5])

added_a = added_s = skipped = 0
for cid, b64 in p_audio.items():
    if cid in audio:
        skipped += 1
        continue
    audio[cid] = b64
    added_a += 1
for t, d in p_say.items():
    for v, cid in d.items():
        if say.get(t, {}).get(v) == cid:
            continue
        say.setdefault(t, {})[v] = cid
        added_s += 1

out = h[:m.start(2)] + json.dumps(VV, ensure_ascii=False) + h[m.end(2):]
fd = os.open(HTML, os.O_WRONLY | os.O_TRUNC)
os.write(fd, out.encode('utf-8'))
os.fsync(fd)
os.close(fd)

# 重讀驗證：JSON 解得開、clip 包的每一筆都真的在裡面、vocab-data 沒被動到
h2 = open(HTML, encoding='utf-8').read()
VV2 = json.loads(re.search(r'<script[^>]*id="vv-data"[^>]*>(.*?)</script>', h2, re.S).group(1))
missing = [cid for cid in p_audio if cid not in VV2['audio']]
assert not missing, '合併後仍缺 %d 個 clip' % len(missing)
vd2 = re.search(r'<script[^>]*id="vocab-data"[^>]*>(.*?)</script>', h2, re.S).group(1)
json.loads(vd2)
assert vd2.count('\n') > 1000, 'vocab-data 的縮排被壓掉了，這會讓 git diff 無法 review'
assert h2.rstrip().endswith('</html>'), '檔案結尾不對'

sz = os.path.getsize(HTML) / 1e6
print('合併完成：新增 %d 個 clip、%d 筆文本對應（跳過已存在 %d 個）' % (added_a, added_s, skipped))
print('vv-data：audio %d → %d、say %d → %d' % (before_a, len(VV2['audio']), before_s, len(VV2['say'])))
print('%s 現在 %.2fMB' % (HTML, sz))
print('提醒：test_voice_full.mjs 裡寫死的 stat.clips 要改成 %d' % len(VV2['audio']))
