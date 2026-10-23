# 安全性政策

## 支援的版本

只有最新的正式版本會收到安全性修正。

| 版本 | 支援 |
|---|---|
| 1.x（最新） | ✅ |
| 更舊的版本 | ❌ |

## 回報漏洞

請不要用公開的 Issue、Pull Request 或討論區回報安全性問題。

請改用 GitHub 的私下回報：到本 repo 的 [Security](https://github.com/tedliou/StreamTurbo/security) 分頁，按 **Report a vulnerability**。請附上：

- 受影響的版本（`streamturbo --version`）與環境（`streamturbo doctor` 的輸出）
- 重現步驟，以及可能造成的影響
- 已知的緩解方式（如果有）

收到後會盡量在一週內回覆，確認問題後修正並發布新版本，並在 Security Advisory 中致謝（除非你希望匿名）。

## 範圍

特別值得回報的是：

- Web Panel 或 OSC 在預設設定（只接受本機連線）下可被其他機器存取
- `--lan` 模式下繞過 access token
- 透過設定檔、Preset 名稱或 OSC 訊息讀寫專案資料夾以外的檔案

sd-turbo、Real-ESRGAN、NDI、Spout 等第三方元件本身的漏洞，請回報給各自的專案。
