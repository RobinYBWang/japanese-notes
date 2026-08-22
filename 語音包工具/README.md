# 語音包工具（VOICEVOX 預錄音檔管線）

給之後的 Claude session 看的操作手冊。用途：筆記新增內容後，補產音檔並寫回 HTML。
搭配專案記憶 `tts.md` 一起讀。

## 現況（2026-08-21）

- **筆記檔＝ `japanese-notes/minna-notes.html`（唯一一份，17.4MB）**。
  2026-08-21 已移除根目錄的中文檔名母版（在 `_to_delete/母版-0821/`）——
  本機用 `file://` 開就是完整編輯模式，從網址開才是唯讀，同一個檔案兩種模式。
- 三角色：Chloe=四国めたん(speaker 2，聲音A預設)、Uncle Ben=青山龍星(13)、
  Darren=玄野武宏(11，聲音B預設)
- vv-data 實測：**say 1655 文本、audio 4965 clips、reading 5 套**，
  Opus 16k mono base64 內嵌在 `<script id="vv-data">`
- 音檔快取**就在 HTML 裡**：不需要另存音檔庫（見「增量更新」）

## 增量更新流程（新增單字/文法/課文後）

1. Stage `japanese-notes/minna-notes.html` 進雲端容器
2. **抽回舊快取**（免重新合成）：解析 `vv-data` JSON，
   把 `audio` map 的每個 `id → base64` 解碼寫成 `opus16/{id}.ogg`
3. 裝 VOICEVOX engine（見下）
4. `node collect_dom.mjs`（走遍每課每分頁收 `data-say`）
5. `python3 gen_full_manifest.py`（產文本清單；**新的課要 port 新的 rtmplN 模板**，
   對照筆記檔裡的 `rtmplN` / `genReadingText` 分支 / `subsFor` 有沒有新分頁）
6. `python3 synth_full.py`（只合成新文本；大批量用 `supervisor.sh` 看門狗）
7. 新 wav 轉 opus：`ffmpeg -c:a libopus -b:a 16k -ac 1`
8. **就地更新 vv-data**：只把 JSON 換成新的 `{say, audio, reading}`，其他一律不動。
   `add_verb_clips.py` 就是這個做法的範本（讀資料 → 算文本 → 只合成缺的 → 塞回 JSON）。
   ⚠️ 舊的 `build_voice_html.py`（母版→語音版的整套外科替換）**已作廢並移出本資料夾**：
   筆記檔本身早就是語音版，那些 assert 一跑就炸。
9. `node test_voice_full.mjs` 全過才交付
10. SendUserFile ＋ `device_commit_files` 覆蓋回 `japanese-notes/minna-notes.html`
    （<20MB 才能 commit，目前 17.4MB）
11. 檔案在 repo 裡 → 照 `CLAUDE.md` 的分支流程 commit（工作分支不 push）

## 本機流程 —— 2026-08-22 起預設走這條

在 Claude Code（本機 Windows）底下，引擎、ffmpeg、合成、合併全在同一台機器上，
所以只要一行：

```
python 語音包工具\本機補音檔.py                      # 預設處理 ..\minna-notes.html
python 語音包工具\本機補音檔.py ..
5-vocab.html
python 語音包工具\本機補音檔.py --engine-only        # 只把引擎叫起來
```

它會依序：找 ffmpeg（PATH 沒有就自己 glob 出來）→ 引擎沒跑就啟動
`vv-engine
un.exe`（無介面、約 4 秒、之後常駐）→ `export_missing_clips.py`
（合成缺的 clip，中途包丟系統暫存）→ `merge_clips.py`（併回 vv-data）。
**缺 0 個就原地結束，HTML 一個字元都不動。**

驗證：

```
node 語音包工具	est_voice_full.mjs [要驗的 html]
```

### 新增一個聲音的成本（2026-08-22 實測，Emily 試作後放棄）

三個聲音 = 1686 個文本 × 3 = 5058 個 clip。**多一個聲音就是整套再來一次 1686 個**。

- 速度：實測 **每個 clip 約 2.5〜3 秒**（引擎單一請求就吃掉約 3.8 顆核心、自己會排隊，
  workers 1／4／8 幾乎沒差；把行程優先權拉高、重啟引擎也沒用）。一個聲音約 **50〜80 分鐘**。
- 體積：**+約 5.8MB**（17.9MB → 約 23.7MB）。
- **陷阱**：`export_missing_clips.py` 的文本來源只有「單字 ＋ data-say」＝ **621 個**，
  vv-data 卻有 **1686 個** —— 差的 1065 個是五十音、朗讀逐行、時間／數字小考的拼讀單位
  （當年由 `gen_full_manifest.py` 那條完整管線產）。
  拿它補新聲音只會補到六成，選了新聲音的人有一大半內容會退回瀏覽器語音。
  真要加聲音，文本清單得**以 vv-data 現有的 say key 為準**，不是重跑 export。

### 本機環境（2026-08-22 裝好）

| 東西 | 位置／版本 |
|---|---|
| VOICEVOX ENGINE | 0.25.2 CPU，`winget install --id HiroshibaKazuyuki.VOICEVOX.CPU`。**解壓縮型套件**，在 `%LOCALAPPDATA%\Microsoft\WinGet\Packages\HiroshibaKazuyuki.VOICEVOX.CPU_*\VOICEVOXv-engine
un.exe`（不是 `Programs\`） |
| ffmpeg | Gyan.FFmpeg 9.0 full（含 libopus） |
| node / playwright | v24.19.0；playwright 裝在本資料夾的 `node_modules`（已 gitignore） |

兩個坑：
- **winget 裝完，當下 shell 的 PATH 還是舊的**，所以腳本自己找 ffmpeg，不靠 PATH。
- **Windows 主控台是 cp950，印日文會 `UnicodeEncodeError` 當掉** →
  `本機補音檔.py` 開頭設 `PYTHONIOENCODING=utf-8`。手動跑子腳本時也要記得帶。

---

## VOICEVOX engine 安裝（雲端容器｜Cowork 時代，留作參考）

- GitHub API 被擋，但 release 直鏈可以下載：
  `https://github.com/VOICEVOX/voicevox_engine/releases/download/0.25.2/voicevox_engine-linux-cpu-x64-0.25.2.7z.001`（1.7GB，7z 解壓）
- 啟動：`./run --host 127.0.0.1 --port 50021`，要等 25〜60 秒
- 大批量合成引擎會掛：用 `supervisor.sh`（掛了重啟＋續跑，已完成自動跳過）
- **陷阱**：`pkill -f 'run --host'` 會殺掉自己的 shell，要用 `pkill -x run`
- 產檔 API：`POST /audio_query?speaker=ID&text=...` → `POST /synthesis?speaker=ID` → wav → ffmpeg
- **只有 Cowork 雲端容器跑得動**。「在使用者電腦」模式無法下載 1.7GB、bash 也無法常駐 engine。

## 補音檔的流程（Cowork 兩段式｜本機不需要，留作參考）

**大檔永遠不要往下走。** 這是整個流程的設計原則，理由是兩個方向的上限不對稱：

| 方向 | 工具 | 上限 |
|---|---|---|
| 使用者電腦 → 雲端 | `device_stage_files` | **400MB** |
| 雲端 → 使用者電腦 | `device_commit_files` | **20MB** ← 只有這邊會卡 |

`minna-notes.html` 已經 17.9MB，用舊做法（雲端改完整份寫回）遲早過不去。
新做法讓 HTML 從頭到尾待在使用者硬碟上，只有幾十 KB 的 clip 包過橋，
檔案漲到 50MB 也一樣能用。

### 步驟

```bash
# 1) 雲端容器：引擎起來後，只匯出缺的 clip，不碰 HTML
python3 export_missing_clips.py <staged 的 minna-notes.html> new-clips.json

# 2) SendUserFile + device_commit_files 把 new-clips.json 送到使用者電腦
#    （放進 japanese-notes\ 底下即可，合併完再 mv 進 _to_delete\）

# 3) 使用者電腦（device_bash）：就地併進 vv-data
python3 語音包工具/merge_clips.py japanese-notes/minna-notes.html new-clips.json
```

實測：`merge_clips.py` 在使用者電腦上處理 17.9MB 的檔案**0.87 秒**跑完，
遠低於 device_bash 每次呼叫 45 秒的上限。

### export_missing_clips.py 的文本來源是兩者的聯集

- **A：`vocab-data`** —— 各課單字的 sayText（漢字優先／`sayForceKana` 強制假名）＋ kana ＋ 動詞活用形
- **B：HTML 原始碼裡所有 `data-say`** —— 文法例句的 🔊 按鈕等

只收 A 會漏掉文法例句（2026-08-22 踩過：新寫的 15 句文法例句一個音檔都沒產）。

**B 有個陷阱**：主程式裡有 `data-say="'+esc(x)+'"`、`data-say="${q.say}"` 這種
**還沒被求值的 JS 樣板字串**。第一版沒過濾就全收去合成，產了 30 個垃圾 clip、
檔案胖 0.6MB。腳本內建 `CODEY` 正規表示式過濾，**不要拿掉**。
（真的混進去了，就從 vv-data 的 `say` 和 `audio` 兩個 map 一起刪掉。）

### merge_clips.py 的保證

- **冪等**：同一個 clip 包重複跑不會出事，已存在的直接跳過（實測過）
- **只動 `<script id="vv-data">`**，用切片繞過整份重寫。
  特別是不會碰到 `<script id="vocab-data">` —— 那是 `indent=2` 的縮排 JSON，
  被壓成一行會讓 `git diff` 變成「-4556 +3」完全無法 review（2026-08-22 踩過）。
  腳本裡有一條 assert 專門擋這件事。
- 合併後重讀驗證：JSON 解得開、clip 包每一筆都真的在裡面、結尾是 `</html>`
- 新的 key 會接在 JSON 尾端（順序跟原本不同，但 vv-data 本來就是壓成一行，diff 無差別）

### 舊的一體式腳本

`add_missing_clips.py`（只有單字）和 `add_datasay_clips.py`（只有 data-say）留著，
它們是「在雲端直接改整份 HTML」的做法，檔案還小或臨時要用時仍可跑。
**新增內容的正規流程請走 export / merge 那條。**

## 關鍵約定（前後端必須一致，錯了不會報錯）

這一節是本資料夾存在的主要理由。以下任何一條跟 HTML 前端對不上，
結果都是「音檔合成成功、寫進檔案、但前端永遠查不到」——沒有錯誤訊息，點下去就是沒聲音。

- clip id = `md5(speaker + '|' + text)` 前 12 碼
- 文本正規化 vvNorm：去掉 `～ ~ ［ ］ [ ]`、全形空白→半形、trim
- 完整性檢查閾值 300 bytes（單一假名的 opus 可能小於 500B）
- 單字唸 sayText（漢字優先，`sayForceKana` 集合強制假名）＋ kana（測驗聽力用）
- 時間/數字小考是**拼讀**：星期/時段/時/分/數字單位各自一個 clip，
  `vvSpeakSegs` 逐段播放。新增這類「獨立發音函式」時要 grep `SpeechSynthesisUtterance`
  和寫死文本的 `speakWith` 呼叫（試聽按鈕教訓），漏掉就會退回瀏覽器語音
- runtime 才產生的文本（如動詞活用）`collect_dom.mjs` 收不到，要自己列舉進 manifest

## 檔案清單

| 檔案 | 用途 |
|---|---|
| collect_dom.mjs | Playwright 走遍全課全分頁收 DOM `data-say` |
| gen_full_manifest.py | 產文本清單＋朗讀套組（rtmpl Python port，固定種子） |
| synth_full.py | 批次合成（cached 自動跳過） |
| supervisor.sh | 引擎看門狗 |
| add_verb_clips.py | 就地更新 vv-data 的範本（動詞活用形補 clip） |
| add_missing_clips.py | **單字**缺音檔一鍵補齊（sayText＋kana＋動詞活用形），add_verb_clips 的超集 |
| add_datasay_clips.py | **HTML 裡所有 `data-say`**（文法例句等）缺音檔一鍵補齊 |
| 本機補音檔.py | **【本機，現在用這支】** 起引擎 → export → merge 一步跑完 |
| export_missing_clips.py | 只匯出缺的 clip 成小 JSON，不改 HTML（單字＋data-say 聯集） |
| merge_clips.py | 把 clip 包併進 vv-data，冪等、就地 |
| test_voice_full.mjs | Playwright 回歸測試（本機版；HTML 路徑吃參數，不再寫死 clip 數）|

## 授權

VOICEVOX 免費可商用，需標註出處。頁尾已有：
「音声：VOICEVOX（四国めたん／青山龍星／玄野武宏）」——換角色時記得同步改。
