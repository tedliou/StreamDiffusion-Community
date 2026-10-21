# StreamTurbo

> **English summary.** StreamTurbo is a Windows-only, real-time image-to-image Runtime for TouchDesigner. It receives video over NDI or Spout, regenerates every frame with a single sd-turbo step on an NVIDIA GPU, and sends the result back over NDI or Spout. Clone the repository and double-click `start.cmd`. It is a non-commercial, independent rewrite of [StreamDiffusion](https://github.com/cumulo-autumn/StreamDiffusion) and is under construction: see the [spec](https://github.com/tedliou/StreamTurbo/issues/2) for the roadmap.

StreamTurbo 是給 TouchDesigner 使用的即時影像生成 Runtime，只支援 Windows。它從 NDI 或 Spout 接收影像，在 NVIDIA 顯示卡上用 sd-turbo 單步重新生成每一格，再經由 NDI 或 Spout 送回去。

> [!NOTE]
> 開發中。目前完成的是 M2：經 NDI 或 Spout 收送影像並即時生成，用 Web Panel、OSC 或 TouchDesigner 範例元件即時調整 Settings，並以 Preset 存取外觀。後續進度請見 [spec #2](https://github.com/tedliou/StreamTurbo/issues/2)。

## 需求

| 項目 | 需求 |
|---|---|
| 作業系統 | Windows 10 / 11 x64 |
| 顯示卡 | NVIDIA RTX 20 系列（Turing）以上，VRAM 8 GB 以上 |
| 驅動程式 | 580 以上 |
| 其他 | git |

不需要另外安裝 Python、CUDA Toolkit、Visual Studio、NDI Tools 或 Node.js。

## 安裝與啟動

```bat
git clone https://github.com/tedliou/StreamTurbo.git
cd StreamTurbo
start.cmd
```

`start.cmd` 依序做這些事：

1. 檢查 NVIDIA 驅動程式版本，太舊就停下並提供更新連結。
2. 把固定版本的 uv 安裝到 `cache\bin`（已安裝就沿用），不使用系統上的其他 uv。
3. 依照 lockfile 同步 Python 3.12 和所有套件（含 CUDA runtime）。第一次執行會下載數 GB。
4. 執行 `streamturbo doctor` 檢查環境。
5. 執行 `streamturbo run`，沿用上次的 Settings 開始生成（第一次是 Glass Preset，NDI 收、NDI 送），並在瀏覽器開啟 Web Panel。第一次執行會下載約 2.3 GB 的模型權重到 `models\`。

`start.cmd` 後面的參數會原封不動交給 `streamturbo run`，例如 `start.cmd --settings spout.toml`。按 Ctrl+C 停止。

所有下載都放在專案資料夾內（`cache\`、`models\`、`.venv\`），刪除資料夾即可完整移除。

## `streamturbo doctor`

回報顯示卡名稱、算力、VRAM、驅動程式版本、目前與預設的功率上限、torch 與 CUDA 版本，以及 NDI 和 Spout 是否可用。環境有問題時結束代碼為 1。

```bat
.venv\Scripts\streamturbo doctor
```

## `streamturbo run`

```bat
.venv\Scripts\streamturbo run
.venv\Scripts\streamturbo run --settings my.toml --preset Glass
.venv\Scripts\streamturbo run --list-sources
```

| 參數 | 說明 |
|---|---|
| （無） | 沿用上次結束時的 Settings（存在 `last-settings.toml`）；第一次執行用 Glass Preset，經 NDI 收送 |
| `--settings 檔案` | 改從這個設定檔開始 |
| `--preset 名稱` | 啟動時套用這個 Preset 的外觀（疊在上面的 Settings 之上） |
| `--list-sources` | 列出目前看得到的 NDI 和 Spout 來源後結束 |
| `--port 8765` | Web Panel 的連接埠 |
| `--lan` | 讓同一個區域網路的平板或手機也能開 Web Panel，需附 access token（見下方） |
| `--osc-port 7000` | 接收 OSC 的連接埠 |
| `--osc-reply 127.0.0.1:7001` | OSC 回報 Settings 和狀態的目的地 |
| `--no-browser` | 啟動時不開瀏覽器 |

執行中每秒更新一行狀態：來源狀態（`waiting` 等待第一格、`live` 正常、`lost` 來源中斷）、每秒輸出格數、生成時間的 p50 和 p95，以及被較新影格取代而丟棄的格數。來源中斷時輸出停在最後一格，來源回來後自動恢復。

### 設定檔

設定檔是 TOML，沒寫的欄位使用 Glass Preset 的預設值。頂層欄位要寫在所有 `[表格]` 之前：

```toml
prompt = "a glass jellyfish, studio lighting"   # 提示詞
strength = 0.68        # 0 只做編解碼，1 完全依提示詞生成（不參考輸入）
seed = 2               # 固定雜訊；調整 strength 不會改變雜訊
fit_mode = "fill"      # 輸入比例不同時：fill 裁切填滿、fit 加黑邊、stretch 拉伸

[source]
transport = "spout"    # ndi、spout，或 none（不收影像，只依提示詞生成）
name = "TD Spout"      # 來源名稱；空字串表示第一個看得到的來源

[sink]
transport = "spout"    # ndi 或 spout
name = "StreamTurbo"   # 送出的名稱
fps = 30               # NDI 宣告的影格率

[generation]           # 生成解析度：256 到 1024，64 的倍數
width = 1024
height = 768

[output]               # 輸出解析度，可與生成解析度不同
width = 1024
height = 768
```

### Settings 的三種類別

每個 Setting 都標示類別，Web Panel 上以標籤顯示：

| 類別 | 欄位 | 套用方式 |
|---|---|---|
| Live | `prompt`、`strength`、`seed` | 下一格就生效，輸出不中斷 |
| Reset | `source.*`、`sink.*`、`generation.*`、`output.*`、`fit_mode` | 重新開啟 Source 或 Sink、重配緩衝區，輸出會停頓一下 |
| Rebuild | （目前沒有） | 需要重建模型 |

一次送出的多個變更會一起套用，不會出現只套用一半的影格。不合法的值會被拒絕，並回報原因，正在跑的 Settings 不受影響。

## Web Panel

`streamturbo run` 啟動後在瀏覽器開啟 <http://127.0.0.1:8765/>。畫面依 Runtime 的 Settings 自動產生，可以：

- 即時調整每個 Setting（Live 的滑桿拖曳時就生效，Reset 的滑桿放開才套用）
- 從清單挑選目前看得到的 NDI 或 Spout 來源
- 看輸入與輸出的預覽、來源狀態、每秒格數、生成時間、VRAM 與顯示卡功耗
- 儲存、套用、重新命名、刪除 Preset
- 切換淺色或深色主題；所有操作都能用鍵盤完成

連線中斷時控制項會停用，Runtime 回來後自動重連。Web Panel 完全離線運作，不從網路載入任何東西。

**在平板上操作**：預設只接受本機連線。加上 `--lan` 後會同時在區域網路上提供，並印出含 access token 的網址（`http://這台電腦的IP:8765/?token=…`）。token 存在 `access-token`，重新啟動後不變，刪除這個檔案就會換一組新的。

## Preset

Preset 是一組外觀：提示詞、strength、seed、fit mode、生成解析度與輸出解析度，不含 Source 和 Sink，所以換場地也能直接套用。

- 內建的 `Glass` 唯讀，放在程式內。
- 自己存的 Preset 是 TOML 檔，放在專案資料夾的 `presets\`，可以直接複製或備份。名稱不分大小寫。
- 在 Web Panel、OSC（`/streamturbo/preset/recall "名稱"`）或啟動時的 `--preset` 都能套用。

## OSC

StreamTurbo 在 7000 埠接收 OSC，並把變更和狀態回報到 127.0.0.1:7001。位址就是 Setting 的路徑：

| 方向 | 位址 | 值 |
|---|---|---|
| 收 | `/streamturbo/prompt`、`/streamturbo/strength`、`/streamturbo/seed` | 一個值 |
| 收 | `/streamturbo/source/transport`、`/streamturbo/source/name`、`/streamturbo/generation/width`…… | 一個值，每個 Setting 都有 |
| 收 | `/streamturbo/preset/recall`、`/streamturbo/preset/save` | Preset 名稱 |
| 收 | `/streamturbo/sync` | 無；要求重送所有 Settings |
| 送 | 與上面相同的 Setting 位址 | 任何 Control Surface 改了 Settings 時送出 |
| 送 | `/streamturbo/status/source_state`、`throughput_fps`、`generation_ms_p50`、`settings_version`、`error` | 每 0.5 秒 |
| 送 | `/streamturbo/error` | 被拒絕的訊息與原因 |

Web Panel 和 OSC 共用同一份 Settings，任一邊的變更另一邊都看得到。

## `streamturbo bench`

用內建測試畫面跑 Glass 工作負載，量測每秒格數、生成時間、峰值 VRAM 和平均功耗，結果寫到 `output\bench\bench-日期-時間.json`，最後一格存成同名 PNG。

```bat
.venv\Scripts\streamturbo bench --frames 120
```

參考值（RTX 3070 功率上限 162 W，1024×768）：約 5.3 fps，生成時間 p50 188 ms，峰值 VRAM 2.8 GiB。

## TouchDesigner 連接

**NDI**（預設）：

1. TouchDesigner 裡用 NDI Out TOP 送出畫面，例如名稱 `TD Out`。
2. 執行 `streamturbo run`。來源名稱留空時接第一個看得到的 NDI 來源；要指定時在設定檔寫 `name = "TD Out"`，或寫完整名稱 `"電腦名稱 (TD Out)"`。
3. 用 NDI In TOP 接收 `電腦名稱 (StreamTurbo)`。

**Spout**（同一台電腦，不壓縮）：

1. TouchDesigner 裡用 Spout Out TOP 送出，例如 Sender Name `TD Spout`。
2. 用上面的設定檔範例執行 `streamturbo run --settings spout.toml`。
3. 用 Spout In TOP 接收 `StreamTurbo`。

**範例元件**：[`touchdesigner/StreamTurbo.tox`](touchdesigner/StreamTurbo.tox) 把上面的步驟包成一個元件，拖進專案即可使用。它的參數頁可以：

- 選擇 Transport（NDI 或 Spout），同時切換送出、接收和 StreamTurbo 的 Source 與 Sink
- 調整 Prompt、Strength、Seed，套用或儲存 Preset（經 OSC）
- 在 Status 頁看來源狀態、每秒格數和生成時間
- 按 Measure Latency 量測 Round-trip Latency

元件有輸入時送出輸入的畫面，沒有時送出動態測試畫面；輸出是 StreamTurbo 回傳的畫面。它由 [`touchdesigner/build_example.py`](touchdesigner/build_example.py) 產生，修改時改這個檔案再重新產生。

**Round-trip Latency**：Measure Latency 讓元件在黑畫面和白畫面之間切換，計時到回傳畫面的亮度跟著改變，重複 10 次取平均。量的是目前的 Settings，包含生成時間。RTX 3070（功率上限 162 W）、Glass Preset、1024×768 的參考值：

| Transport | 平均 | 最小 | 最大 |
|---|---|---|---|
| NDI | 555–579 ms | 433 ms | 694 ms |
| Spout | 441 ms | 344 ms | 709 ms |

這時生成約 230 ms 一格（約 4.4 fps），延遲大部分來自生成本身和等待中的影格。速度優化是下一個里程碑的工作。

已知限制：Spout 沒有開啟 frame counting 時，StreamTurbo 無法分辨畫面是否更新。這時把 TouchDesigner 的 Spout Out 設為 inactive，狀態仍會顯示 `live`；刪除 Spout Out TOP 才會變成 `lost`。frame counting 是 Spout 的全系統設定（SpoutSettings 工具），StreamTurbo 不會改動它。

## 疑難排解

| 狀況 | 處理方式 |
|---|---|
| Web Panel 打不開 | 確認 `streamturbo run` 還在執行，或埠號被占用時改用 `--port` |
| 平板顯示需要 access token | 用 `--lan` 啟動時印出的完整網址，包含 `?token=` |
| Spout Out 顯示 Sender Name 已被使用 | 換一個名稱，或重新啟動 TouchDesigner 釋放殘留的名稱 |
| 顯示找不到 NVIDIA 驅動程式 | 從 [NVIDIA 官網](https://www.nvidia.com/Download/index.aspx) 安裝 580 以上的驅動程式 |
| uv 安裝失敗 | 確認網路連線，或手動安裝 [uv](https://docs.astral.sh/uv/) 後重新執行 |
| `doctor` 顯示 NOT READY | 依照 PROBLEM 那幾行的說明處理 |
| 狀態一直是 `waiting` | 用 `streamturbo run --list-sources` 確認來源名稱，NDI 另需確認防火牆允許 |
| 每秒格數偏低 | 確認沒有其他程式占用顯示卡，並用 `doctor` 檢查功率上限 |

## 開發

```bat
uv sync
uv run ruff check
uv run ruff format --check
uv run pyright
uv run pytest -m "not gpu"
```

Web Panel 的原始碼在 `web\`（React + Vite），建置結果提交在 `src\streamturbo\web_panel`，使用者不需要 Node.js。修改 Web Panel 後：

```bat
cd web
npm ci
npm run lint
npm run build
```

CI 會確認提交的建置結果與原始碼一致。介面設計規範見 [DESIGN.md](DESIGN.md)。

設計文件：[GLOSSARY.md](GLOSSARY.md)、[docs/adr/](docs/adr/)。

## 授權

- 程式碼採用 [Apache-2.0](LICENSE)，源自 StreamDiffusion，詳見 [NOTICE](NOTICE)。
- sd-turbo 模型權重另採 Stability AI Community License，商業使用須遵守該授權條款。本專案本身以非商業用途開發。
- NDI® 是 Vizrt NDI AB 的註冊商標，詳見 [ndi.video](https://ndi.video)。
