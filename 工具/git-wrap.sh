#!/usr/bin/env bash
# 這個 repo 專用的 git 包裝。存在的理由是 device_bash 沒有刪檔權限：
#   1. git 自己也刪不掉它建的 .lock，導致「第二個 git 指令一定失敗」
#   2. 切換分支時 git 刪不掉舊分支才有的檔案，導致 checkout / merge 直接爆掉
# 所以：一律用 g 下指令，上線一律用 publish（不切分支）。
#
# 用法（每個 device_bash call 都要先 source，shell 不延續）：
#   source "$(ls -d $HOME/mnt/日文學習)/japanese-notes/工具/git-wrap.sh"
#   g status -sb
#   g add -- minna-notes.html
#   g commit -m '第5課單字'
#   publish '第5課上線'          # 把目前分支壓成一筆推進 main
#
# 鐵律：絕不直接下 raw git，絕不 git checkout 切分支。

_GW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_GW_REPO="$_GW_ROOT/japanese-notes"
_GW_NAME='RobinYBWang'
_GW_MAIL='46957897+RobinYBWang@users.noreply.github.com'

# git 留下的 .lock / tmp_obj 刪不掉，只能搬走。每次 git 前後都掃一次。
sweep_locks() {
  local trash="$_GW_ROOT/_to_delete/git殘留-$(date +%m%d)"
  local f moved=0
  while IFS= read -r f; do
    [ -e "$f" ] || continue
    mkdir -p "$trash"
    mv "$f" "$trash/$(printf '%s' "${f#$_GW_REPO/.git/}" | tr '/' '_').$$-$RANDOM" 2>/dev/null && moved=$((moved+1))
  done < <(find "$_GW_REPO/.git" \( -name '*.lock' -o -name 'tmp_obj_*' \) 2>/dev/null)
  [ "$moved" -gt 0 ] && echo "[git-wrap] 清掉 $moved 個殘留" >&2
  return 0
}

g() {
  sweep_locks
  git -C "$_GW_REPO" -c user.name="$_GW_NAME" -c user.email="$_GW_MAIL" "$@"
  local rc=$?
  sweep_locks
  return $rc
}

# 把目前分支的「內容」壓成一筆接到 main 上。
# 用 commit-tree 而不是 checkout main + merge --squash，因為切分支在這個環境會失敗
# （git 刪不掉工作分支才有的檔案）。這個做法完全不動工作目錄，也不換分支。
publish() {
  local msg="$1"
  if [ -z "$msg" ]; then echo "用法：publish '上線訊息'" >&2; return 2; fi
  local dirty; dirty=$(git -C "$_GW_REPO" status --porcelain 2>/dev/null)
  if [ -n "$dirty" ]; then
    echo "[publish] 中止：工作目錄還有沒 commit 的東西" >&2
    printf '%s\n' "$dirty" >&2; sweep_locks; return 1
  fi
  local br; br=$(git -C "$_GW_REPO" symbolic-ref --short HEAD 2>/dev/null)
  if [ "$br" = "main" ]; then echo "[publish] 中止：現在人就在 main，publish 是給工作分支用的" >&2; return 1; fi
  local new
  new=$(git -C "$_GW_REPO" -c user.name="$_GW_NAME" -c user.email="$_GW_MAIL" \
        commit-tree "$br^{tree}" -p main -m "$msg") || { sweep_locks; return 1; }
  git -C "$_GW_REPO" update-ref refs/heads/main "$new" || { sweep_locks; return 1; }
  sweep_locks
  echo "[publish] main → ${new:0:7}（$br 的內容壓成一筆）"
  git -C "$_GW_REPO" diff --numstat main "$br" | grep -q . \
    && echo "[publish] ⚠ main 與 $br 內容不一致，請檢查" >&2 \
    || echo "[publish] 驗證通過：main 與 $br 內容完全一致"
  echo "[publish] 接下來換你：在 GitHub Desktop 或自己的終端機 push main"
  sweep_locks
}
