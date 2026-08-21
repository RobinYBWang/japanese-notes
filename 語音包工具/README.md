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

## VOICEVOX engine 安裝（雲端容器）

- GitHub API 被擋，但 release 直鏈可以下載：
  `https://github.com/VOICEVOX/voicevox_engine/releases/download/0.25.2/voicevox_engine-linux-cpu-x64-0.25.2.7z.001`（1.7GB，7z 解壓）
- 啟動：`./run --host 127.0.0.1 --port 50021`，要等 25〜60 秒
- 大批量合成引擎會掛：用 `supervisor.sh`（掛了重啟＋續跑，已完成自動跳過）
- **陷阱**：`pkill -f 'run --host'` 會殺掉自己的 shell，要用 `pkill -x run`
- 產檔 API：`POST /audio_query?speaker=ID&text=...` → `POST /synthesis?speaker=ID` → wav → ffmpeg
- **只有 Cowork 雲端容器跑得動**。「在使用者電腦」模式無法下載 1.7GB、bash 也無法常駐 engine。

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
| test_voice_full.mjs | Playwright 回歸測試 |

## 授權

VOICEVOX 免費可商用，需標註出處。頁尾已有：
「音声：VOICEVOX（四国めたん／青山龍星／玄野武宏）」——換角色時記得同步改。
