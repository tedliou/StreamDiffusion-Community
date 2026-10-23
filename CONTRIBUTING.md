# 參與開發

## 開始之前

- 用語以 [GLOSSARY.md](GLOSSARY.md) 為準，架構決策記在 [docs/adr/](docs/adr/)。
- 先開 Issue 討論，再開 Pull Request。Issue 的標籤與分流方式見 [docs/agents/triage-labels.md](docs/agents/triage-labels.md)。
- 錯誤回報請用 Issue 範本，並附上 `streamturbo doctor` 的輸出。

## 開發環境與檢查

開發用的命令見 [README 的開發章節](README.md#開發)。提交前請確認這些都通過（CI 也會檢查）：

```bat
uv run ruff check
uv run ruff format --check
uv run pyright
uv run pytest -m "not gpu"
```

需要 GPU 與真實模型的測試標成 `gpu`，CI 不會執行，請在本機跑 `uv run pytest`。修改 Web Panel 後要重新建置並提交 `src\streamturbo\web_panel`。

## 分支與 Pull Request

- 一個 Issue 一個分支、一個 Pull Request，描述裡寫 `Closes #編號`。
- `main` 受分支規則保護：只能經 Pull Request 合併，且 CI 的 `check` 必須通過。
- Commit 訊息用英文的 [Conventional Commits](https://www.conventionalcommits.org/)，例如 `feat: …`、`fix: …`、`docs: …`。

## 發布流程

版本號依照 [Semantic Versioning](https://semver.org/lang/zh-TW/)，公開介面的定義見 [CHANGELOG.md](CHANGELOG.md) 開頭。本 repo 開啟了 immutable releases：發布後的 tag 與 release 無法移動或重用，發錯版本只能再發下一版修正。

1. 開一個發布用的分支，更新：
   - `pyproject.toml` 的 `version`，再執行 `uv lock` 更新 `uv.lock`
   - `web/package.json` 的 `version`（`npm version X.Y.Z --no-git-tag-version`）
   - `CHANGELOG.md`：把 `[Unreleased]` 的內容移到新版本，並更新底部的比較連結
   - `README.md` 安裝與更新章節裡的 tag
2. 開 Pull Request，CI 通過後合併。
3. 在合併後的 `main` 上建立附註 tag 並推送：

   ```bat
   git switch main
   git pull --ff-only
   git tag -a vX.Y.Z -m "StreamTurbo vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. 以該版本的 CHANGELOG 內容建立 GitHub Release：

   ```bat
   gh release create vX.Y.Z --verify-tag --title "StreamTurbo vX.Y.Z" --notes-file 版本說明.md
   ```

`v*` tag 受規則保護，無法刪除或移動。
