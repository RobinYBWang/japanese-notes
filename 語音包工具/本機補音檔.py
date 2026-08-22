# 本機補音檔.py —— 【在使用者電腦上一步跑完】補齊某個 HTML 缺的 VOICEVOX 音檔
#
# 這支是 Claude Code（本機）時代的入口。Cowork 時代要拆成
#   export_missing_clips.py（雲端合成）→ 檔案過橋 → merge_clips.py（本機合併）
# 是因為 device_commit_files 有 20MB/檔的限制；在本機兩件事都在同一台機器上，
# 所以這支直接把兩段接起來，中間的 clip 包丟到暫存資料夾。
#
# 執行：
#   python 本機補音檔.py                      # 預設處理 ..\minna-notes.html
#   python 本機補音檔.py ..\n5-vocab.html
#   python 本機補音檔.py --engine-only        # 只把引擎叫起來，不合成
#
# 注意：這條路徑只補「單字 ＋ HTML 的 data-say」＝ 621 個文本，
#   但 vv-data 實際有 1686 個（多的是五十音、朗讀逐行、時間／數字小考的拼讀單位，
#   那些當年是 gen_full_manifest.py 那條完整管線產的）。
#   日常新增課文用這支沒問題；**要新增一個聲音**的話這樣補只會到六成，見 README。
#
# 前置：VOICEVOX（CPU 版）已安裝、ffmpeg 在 PATH 上。
#   引擎會由這支自動啟動（無介面，就是 VOICEVOX 內附的 vv-engine\run.exe），
#   啟動後會繼續常駐，之後再跑就是秒開。
#
import glob, json, os, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'http://127.0.0.1:50021'

# 這幾支都會印日文；Windows 主控台預設 cp950，不改編碼會 UnicodeEncodeError 當掉。
os.environ['PYTHONIOENCODING'] = 'utf-8'
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# winget 的 VOICEVOX.CPU 是「解壓縮型」套件，裝在 WinGet\Packages 底下（不是 Programs\）。
ENGINE_GLOBS = [
    os.path.expandvars(p) for p in (
        r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\*VOICEVOX*\VOICEVOX\vv-engine\run.exe',
        r'%LOCALAPPDATA%\Programs\VOICEVOX\vv-engine\run.exe',
        r'%PROGRAMFILES%\VOICEVOX\vv-engine\run.exe',
    )
]


FFMPEG_GLOBS = [
    os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe'),
]


def find_engine():
    for g in ENGINE_GLOBS:
        hits = sorted(glob.glob(g))
        if hits:
            return hits[0]
    return None


def ensure_ffmpeg():
    """export 那支直接呼叫 `ffmpeg`。winget 剛裝完的那個 session PATH 還是舊的，
    所以自己找一次、補進 PATH，免得跑到一半才炸。"""
    if shutil.which('ffmpeg'):
        return
    for g in FFMPEG_GLOBS:
        hits = sorted(glob.glob(g))
        if hits:
            os.environ['PATH'] = os.path.dirname(hits[0]) + os.pathsep + os.environ['PATH']
            print('ffmpeg 不在 PATH 上，改用 %s' % hits[0])
            return
    sys.exit('找不到 ffmpeg。裝法：winget install --id Gyan.FFmpeg -e')


def engine_alive(timeout=2):
    try:
        with urllib.request.urlopen(BASE + '/version', timeout=timeout) as r:
            return r.read().decode().strip().strip('"')
    except Exception:
        return None


def start_engine(wait=240):
    exe = find_engine()
    if not exe:
        sys.exit('找不到 VOICEVOX 引擎（vv-engine\\run.exe）。找過：\n  ' +
                 '\n  '.join(ENGINE_GLOBS))
    print('啟動引擎：%s' % exe)
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP：跟本行程脫鉤，之後常駐
    flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0
    log = open(os.path.join(tempfile.gettempdir(), 'voicevox_engine.log'), 'ab')
    subprocess.Popen([exe, '--host', '127.0.0.1', '--port', '50021'],
                     cwd=os.path.dirname(exe), stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < wait:
        v = engine_alive()
        if v:
            print('引擎起來了（%.0f 秒），version %s' % (time.time() - t0, v))
            return v
        time.sleep(2)
    sys.exit('引擎在 %d 秒內沒有回應，看 %s' %
             (wait, os.path.join(tempfile.gettempdir(), 'voicevox_engine.log')))


def ensure_engine():
    v = engine_alive()
    if v:
        print('引擎已在跑，version %s' % v)
        return v
    return start_engine()


def run(script, *args):
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    print('\n$ %s' % ' '.join(os.path.basename(c) for c in cmd))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode:
        sys.exit('%s 失敗（exit %d）' % (script, r.returncode))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--engine-only' in sys.argv:
        ensure_engine()
        return
    html = os.path.abspath(args[0]) if args else os.path.join(HERE, '..', 'minna-notes.html')
    html = os.path.normpath(html)
    if not os.path.exists(html):
        sys.exit('找不到 %s' % html)
    print('目標檔案：%s（%.2fMB）' % (html, os.path.getsize(html) / 1e6))

    ensure_ffmpeg()
    ensure_engine()
    pack = os.path.join(tempfile.gettempdir(), 'new-clips.json')
    run('export_missing_clips.py', html, pack)
    if not json.load(open(pack, encoding='utf-8')).get('audio'):
        print('\n沒有缺的音檔，HTML 一個字元都沒動。')
        return
    run('merge_clips.py', html, pack)
    print('\n完成。接著驗證：')
    print('  node "%s" "%s"' % (os.path.join(HERE, 'test_voice_full.mjs'), html))


if __name__ == '__main__':
    main()
