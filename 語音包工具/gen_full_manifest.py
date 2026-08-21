# 全站發音文本清單:DOM data-say + 單字 sayText/kana + 五十音 + 朗讀預生成套組
import json, re, random, hashlib

VOICES = [2, 11, 13]
SETS_PER_LESSON = 3   # L1-L3 朗讀套數
TOTAL_SETS = 2        # 總朗讀套數

src = open('/mnt/user-data/uploads/日文學習/japanese-notes/minna-notes.html', encoding='utf-8').read()
wb = json.loads(re.search(r'<script[^>]*id="vocab-data"[^>]*>(.*?)</script>', src, re.S).group(1))
dom_says = json.load(open('/home/claude/full/dom_says.json', encoding='utf-8'))

STRIP = re.compile(r'[～~［］\[\]]')
def norm(t):  # 與網頁端 lookup 一致
    return STRIP.sub('', str(t or '')).replace('　', ' ').strip()

SAY_FORCE_KANA = {'車','何','薬','家','百','千','101','眼鏡','梅酒','夜市','元','何階','木','鈴'}
def say_text(r):  # port 自母版 sayText
    w = STRIP.sub('', (r.get('word') or '')).strip()
    if w and w not in SAY_FORCE_KANA:
        return w
    return re.sub(r'\s*\n\s*', '、', (r.get('kana') or '').replace('～','').replace('~','')).strip()

texts = set()
def add(t):
    t = norm(t)
    if t: texts.add(t)

# 1) DOM data-say(文法/數字/量詞/時間/測驗靜態部分)
for t in dom_says: add(t)

# 2) 單字:sayText + kana(測驗聽力題用 r.kana)
for k, rows in wb['lessons'].items():
    if k == '0': continue
    for r in rows:
        add(say_text(r)); add(r.get('kana'))

# 3) 五十音:hira/kata/例詞(（ 前)
for r in wb['lessons'].get('0', []):
    add(r.get('hira')); add(r.get('kata'))
    for f in ('hiraex', 'kataex'):
        ex = (r.get(f) or '').split('（')[0]
        add(ex)

# 4) 朗讀預生成 —— port 自母版 rtmpl1/2/3 + cycleTemplates + buildReading1/2/3 + genTotalReading
READ_NAMES = ['田中','佐藤','鈴木','山田','キム','スミス','リン']
AGES = [f'{i}歳' for i in range(1, 100)]
BAD = re.compile(r'[〜～\[\]［］]')
def pos_words(rs, p):
    out = []
    for r in rs:
        if r.get('pos') == p:
            w = r.get('word') or r.get('kana')
            if w and w not in out: out.append(w)
    return out

def rtmpl1(rs, rng):
    J = pos_words(rs, 'job'); C = pos_words(rs, 'country')
    if len(J) < 2: return []
    nm = lambda: rng.choice(READ_NAMES)
    def rj(e):
        o = [x for x in J if x != e]; return rng.choice(o if o else J)
    rc = lambda: rng.choice(C) if C else '日本'
    age = lambda: rng.choice(AGES[17:60])
    return [
        lambda: ['A: あの人は 誰ですか。', 'B: ' + nm() + 'さんです。'],
        lambda: (lambda n, j: ['A: ' + n + 'さんは ' + j + 'ですか。', 'B: はい、' + j + 'です。'])(nm(), rng.choice(J)),
        lambda: (lambda n, j: ['A: ' + n + 'さんは ' + j + 'ですか。', 'B: いいえ、' + j + 'じゃ ありません。' + rj(j) + 'です。'])(nm(), rng.choice(J)),
        lambda: (lambda n: ['A: お名前は 何ですか。', 'B: ' + n + 'です。'])(nm()),
        lambda: (lambda n, c: ['A: ' + n + 'さんは ' + c + '人ですか。', 'B: はい、' + c + '人です。'])(nm(), rc()),
        lambda: (lambda n, j: ['A: ' + n + 'さんも ' + j + 'ですか。', 'B: はい、' + n + 'さんも ' + j + 'です。'])(nm(), rng.choice(J)),
        lambda: (lambda n: ['A: あの人は 誰ですか。', 'B: 私の 友達の ' + n + 'さんです。'])(nm()),
        lambda: ['A: 何歳ですか。', 'B: ' + age() + 'です。'],
        lambda: ['A: おいくつですか。', 'B: ' + age() + 'です。'],
        lambda: (lambda n: ['A: ' + n + 'さんは 何歳ですか。', 'B: ' + n + 'さんは ' + age() + 'です。'])(nm()),
    ]

def rtmpl2(rs, rng):
    N = pos_words(rs, 'n')
    if len(N) < 3: return []
    nm = lambda: rng.choice(READ_NAMES)
    dem = lambda: rng.choice(['これ', 'それ', 'あれ'])
    kono = lambda: rng.choice(['この', 'その', 'あの'])
    flip = {'これ': 'それ', 'それ': 'これ', 'あれ': 'あれ'}
    def rn(e=None):
        x = rng.choice(N); g = 0
        while e and x == e and g < 6: x = rng.choice(N); g += 1
        return x
    return [
        lambda: (lambda d, n: ['A: ' + d + 'は 何ですか。', 'B: ' + flip[d] + 'は ' + n + 'です。'])(dem(), rn()),
        lambda: (lambda d, n: ['A: ' + d + 'は ' + n + 'ですか。', 'B: はい、そうです。' + n + 'です。'])(dem(), rn()),
        lambda: (lambda d, n: ['A: ' + d + 'は ' + n + 'ですか。', 'B: いいえ、違います。' + rn(n) + 'です。'])(dem(), rn()),
        lambda: (lambda d, n, n2: ['A: ' + d + 'は ' + n + 'ですか、それとも ' + n2 + 'ですか。', 'B: ' + rng.choice([n, n2]) + 'です。'])(dem(), rn(), rn()),
        lambda: (lambda d, n: ['A: ' + d + 'は 誰の ' + n + 'ですか。', 'B: ' + nm() + 'さんの ' + n + 'です。'])(dem(), rn()),
        lambda: (lambda n: ['A: この' + n + 'は 誰のですか。', 'B: ' + nm() + 'さんのです。'])(rn()),
        lambda: (lambda k, n: ['A: ' + k + n + 'は 誰のですか。', 'B: 私のです。'])(kono(), rn()),
    ]

def rtmpl3(rs, rng):
    P = [w for w in pos_words(rs, 'place') if w and not BAD.search(w)]
    C = [w for w in pos_words(rs, 'country') if w and not BAD.search(w)]
    N = [w for w in pos_words(rs, 'n') if w and not BAD.search(w)]
    if len(P) < 2: return []
    flipP = {'ここ': 'そこ', 'そこ': 'ここ', 'あそこ': 'あそこ'}
    demP = lambda: rng.choice(['ここ', 'そこ', 'あそこ'])
    here = lambda: rng.choice(['ここ', 'そこ', 'あそこ'])
    rp = lambda: rng.choice(P)
    def rp2(e):
        x = rng.choice(P); g = 0
        while e and x == e and g < 6: x = rng.choice(P); g += 1
        return x
    rc = lambda: rng.choice(C) if C else '台湾'
    rn = lambda: rng.choice(N)
    T = [
        lambda: (lambda d, p: ['A: ' + d + 'は 何ですか。', 'B: ' + flipP[d] + 'は ' + p + 'です。'])(demP(), rp()),
        lambda: (lambda p: ['A: ' + p + 'は どこですか。', 'B: ' + here() + 'です。'])(rp()),
        lambda: (lambda p: ['A: すみません、' + p + 'は どこですか。', 'B: ' + here() + 'です。'])(rp()),
        lambda: (lambda p: ['A: ' + p + 'は どこですか。', 'B: ' + rp2(p) + 'の 近くです。'])(rp()),
        lambda: (lambda d, p: ['A: ' + d + 'は ' + p + 'ですか。', 'B: はい、そうです。' + p + 'です。'])(demP(), rp()),
        lambda: (lambda d, p: ['A: ' + d + 'は ' + p + 'ですか。', 'B: いいえ、違います。' + rp2(p) + 'です。'])(demP(), rp()),
        lambda: (lambda p: ['A: ' + p + 'は どちらですか。', 'B: あちらです。'])(rp()),
    ]
    if C:
        T.append(lambda: ['A: お国は どちらですか。', 'B: ' + rc() + 'です。'])
        T.append(lambda: (lambda c: ['A: これは どこの 車ですか。', 'B: ' + c + 'の 車です。'])(rc()))
    if N:
        T.append(lambda: (lambda n, y: ['A: ' + n + 'は いくらですか。', 'B: ' + y + '円です。'])(rn(), rng.choice(['500', '980', '1500', '3000', '5000'])))
        T.append(lambda: (lambda n, y: ['A: ' + n + 'は いくらですか。', 'B: ' + y + '円くらいです。'])(rn(), rng.choice(['1000', '2000', '8000'])))
    return T


DAYS4=[['月曜日','げつようび'],['火曜日','かようび'],['水曜日','すいようび'],['木曜日','もくようび'],['金曜日','きんようび'],['土曜日','どようび'],['日曜日','にちようび']]
def rtmpl4(rs, rng):
    V=[r for r in (rs or []) if (r.get('kana') or '').endswith('ます') and (r.get('word') or '')]
    if len(V)<2: return []
    rv=lambda: rng.choice(V); day=lambda: rng.choice(DAYS4); hr=lambda: 1+rng.randrange(12)
    cj=lambda r,suf: re.sub(r'ます$','',(r.get('word') or ''))+suf
    def t1():
        h=hr(); m=rng.randrange(60); ap=rng.random()<0.5
        return ['A: 今 何時ですか。','B: '+('午前' if ap else '午後')+' '+str(h)+'時'+((str(m)+'分') if m else '')+'です。']
    T=[
        t1,
        lambda: (lambda d: ['A: 今日は 何曜日ですか。','B: '+d[0]+'です。'])(day()),
        lambda: (lambda h1,h2: ['A: 銀行は 何時から 何時までですか。','B: '+str(h1)+'時から '+str(h2)+'時までです。'])(hr(),hr()),
        lambda: (lambda r,h: ['毎日 '+str(h)+'時に '+cj(r,'ます')+'。'])(rv(),hr()),
        lambda: (lambda r: ['昨日 '+cj(r,'ました')+'。'])(rv()),
        lambda: (lambda r,d: [d[0]+'は '+cj(r,'ません')+'。'])(rv(),day()),
        lambda: ['A: 休みは 何曜日ですか。','B: 休みは 土曜日と 日曜日です。'],
        lambda: ['A: 大変ですね。','B: そうですね。'],
    ]
    return T

def cycle(T, target, rng):
    L = []; g = 0
    while len(L) < target and g < 25:
        for f in T:
            if len(L) >= target: break
            L.extend(f())
        g += 1
    return L

def build_lesson_reading(n, rng):
    rs = wb['lessons'].get(str(n), [])
    if n == 1:
        T = rtmpl1(rs, rng)
        if not T: return []
        L = ['A: はじめまして。', 'B: はじめまして。どうぞ よろしく お願いします。'] + cycle(T, 50, rng)
        L += ['A: いろいろ ありがとう ございました。', 'B: いいえ、どういたしまして。']
        return L
    if n == 3:
        T = rtmpl3(rs, rng); return cycle(T, 52, rng) if T else []
    if n == 4:
        T = rtmpl4(rs, rng); return cycle(T, 52, rng) if T else []
    T = rtmpl2(rs, rng); return cycle(T, 52, rng) if T else []

def all_rows():
    out = []
    for k, rows in wb['lessons'].items():
        if k not in ('0', '13'): out.extend(rows)
    return out

def build_total(rng):
    rs = all_rows()
    T = rtmpl1(rs, rng) + rtmpl2(rs, rng) + rtmpl3(rs, rng) + rtmpl4(rs, rng)
    if not T: return []
    ex = []; g = 0
    while len(ex) < 50 and g < 400:
        pr = rng.choice(T)()
        if pr: ex.append(pr)
        g += 1
    rng.shuffle(ex)
    return [x for pr in ex for x in pr]

reading = {}
for n in (1, 2, 3, 4):
    sets = []
    for si in range(SETS_PER_LESSON):
        lines = build_lesson_reading(n, random.Random(1000 * n + si))
        sets.append(lines)
        for ln in lines: add(re.sub(r'^[AB]:\s*', '', ln))
    reading[str(n)] = ['\n'.join(s) for s in sets]
tsets = []
for si in range(TOTAL_SETS):
    lines = build_total(random.Random(9900 + si))
    tsets.append(lines)
    for ln in lines: add(re.sub(r'^[AB]:\s*', '', ln))
reading['99'] = ['\n'.join(s) for s in tsets]


# 5) 時間小考+數字小考的拼讀單位
DAY_KN=['げつようび','かようび','すいようび','もくようび','きんようび','どようび','にちようび']
PERIOD_KN=['ごぜん','ごご','あさ','ひる','ゆうがた','よる','よなか']
PERIOD_NO=['あさの','ひるの','ゆうがたの','よるの','よなかの']
HOUR_KANA=['','いちじ','にじ','さんじ','よじ','ごじ','ろくじ','しちじ','はちじ','くじ','じゅうじ','じゅういちじ','じゅうにじ']
def min_kana(m):
    one={1:'いっぷん',2:'にふん',3:'さんぷん',4:'よんぷん',5:'ごふん',6:'ろっぷん',7:'ななふん',8:'はっぷん',9:'きゅうふん'}
    tensX={1:'じゅっぷん',2:'にじゅっぷん',3:'さんじゅっぷん',4:'よんじゅっぷん',5:'ごじゅっぷん'}
    tensP={1:'じゅう',2:'にじゅう',3:'さんじゅう',4:'よんじゅう',5:'ごじゅう'}
    if m==0: return ''
    if m<10: return one[m]
    t,o=divmod(m,10)
    return tensX[t] if o==0 else tensP[t]+one[o]
NUM_ONES=['','いち','に','さん','よん','ご','ろく','なな','はち','きゅう']
NUM_JUU=['','じゅう','にじゅう','さんじゅう','よんじゅう','ごじゅう','ろくじゅう','ななじゅう','はちじゅう','きゅうじゅう']
NUM_HYAKU=['','ひゃく','にひゃく','さんびゃく','よんひゃく','ごひゃく','ろっぴゃく','ななひゃく','はっぴゃく','きゅうひゃく']
NUM_SEN=['','せん','にせん','さんぜん','よんせん','ごせん','ろくせん','ななせん','はっせん','きゅうせん']
for t in DAY_KN+PERIOD_KN+PERIOD_NO: add(t)
for h in range(1,13): add(HOUR_KANA[h])
for m in range(1,60): add(min_kana(m))
add('ゼロ')
for i in range(1,10):
    add(NUM_ONES[i]+'まん'); add(NUM_SEN[i]); add(NUM_HYAKU[i])
for n in range(1,100):
    add(NUM_JUU[n//10]+NUM_ONES[n%10])


# 6) 語音設定的試聽句
add('あめ、はし、かぎ、にほんご。はつおんテストです。')
add('こんにちは。べつの こえで はなします。')

# 7) 動詞小考:各課「ます」動詞 × 四種活用形(kana，vbPool 播 vbRow.kana)
#    ます形本身多半已在單字裡；ません/ました/ませんでした 才是缺的
VERB_SUFS = ['ます', 'ません', 'ました', 'ませんでした']
for k, rows in wb['lessons'].items():
    if k in ('0', '13', '14'): continue
    for r in rows:
        ka = r.get('kana') or ''
        if ka.endswith('ます') and 2 < len(ka) <= 9:  # 排除「どうぞ…おねがいします」等長片語
            stem = ka[:-2]
            for s in VERB_SUFS:
                add(stem + s)

def aid(text, speaker):
    return hashlib.md5((str(speaker) + '|' + text).encode()).hexdigest()[:12]

utter = {}; say = {}
for t in sorted(texts):
    say[t] = {}
    for v in VOICES:
        k = aid(t, v)
        utter[k] = {'text': t, 'speaker': v}
        say[t][str(v)] = k

json.dump({'utter': utter, 'say': say, 'reading': reading},
          open('/home/claude/full/manifest_full.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('texts', len(texts), 'clips', len(utter), 'reading sets', {k: len(v) for k, v in reading.items()})
