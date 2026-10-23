# 變更紀錄

本檔記錄每個版本的重要變更，格式依照 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依照 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

版本號的公開介面是：設定檔與 Preset 的格式、OSC 位址、`streamturbo` 命令列參數，以及 `start.cmd` 的用法。這些有不相容的變更時升主版本號。

## [Unreleased]

## [1.0.0] - 2026-10-24

第一個正式版本。StreamTurbo 是從 StreamDiffusion 獨立出來重寫的專案（[ADR-0009](docs/adr/0009-independent-fork.md)），不相容於上游。

### 新增

- **Runtime**：經 NDI 或 Spout 接收影像，在 NVIDIA 顯示卡上用 sd-turbo 單步生成，再經 NDI 或 Spout 送回；只處理最新影格，來源中斷時停在最後一格並自動恢復。
- **一鍵啟動**：`start.cmd` 檢查驅動程式、安裝固定版本的 uv、依 lockfile 同步 Python 與套件、執行 `streamturbo doctor` 後開始生成。所有下載都留在專案資料夾內。
- **TensorRT Backend**：UNet、tiny VAE 與 Upscaler 的 Engine 在本機背景建置，建置期間先用 PyTorch 輸出，建好後自動切換；依顯示卡與 TensorRT 版本分開快取。`streamturbo build-engines` 可在演出前先建好。
- **Live control**：Settings 分成 Live、Reset、Rebuild 三類，從 Web Panel、OSC 或 TouchDesigner 範例元件即時調整，一次送出的變更整批套用；Preset 儲存與套用外觀。
- **Web Panel**：依 Settings 自動產生的控制介面，含預覽、狀態、Preset 管理、淺色與深色主題；完全離線，`--lan` 可讓平板以 access token 連線。
- **畫面品質**：Prompt Blend（多個帶權重的提示詞）、Temporal Smoothing、Temporal Coherence，以及提示詞與 strength 的平滑漸變；Similar Frame Skip 在靜態畫面時降低功耗。
- **Upscaler**：輸出解析度大於生成解析度時，用 Real-ESRGAN 的小型模型放大並補出細節。
- **Low-VRAM Mode**：4–6 GB VRAM 的顯示卡自動進入，Engine 建置時獨占顯示卡，Generation Resolution 上限每邊 512，由 Upscaler 放大到輸出解析度。`--low-vram`、`--no-low-vram` 可強制開關。
- **TouchDesigner 範例元件**：`touchdesigner/StreamTurbo.tox`，切換 NDI 或 Spout、調整 Prompt 與 strength、量測 Round-trip Latency。
- **`streamturbo bench`**：量測每秒格數、生成時間、峰值 VRAM 與功耗，並可跑品質/速度矩陣。

[Unreleased]: https://github.com/tedliou/StreamTurbo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tedliou/StreamTurbo/releases/tag/v1.0.0
