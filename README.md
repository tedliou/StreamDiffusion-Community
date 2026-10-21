# StreamTurbo

> **English summary.** StreamTurbo is a Windows-only, real-time image-to-image Runtime for TouchDesigner. It receives video over NDI or Spout, regenerates every frame with a single sd-turbo step on an NVIDIA GPU, and sends the result back over NDI or Spout. Clone the repository and double-click `start.cmd`. It is a non-commercial, independent rewrite of [StreamDiffusion](https://github.com/cumulo-autumn/StreamDiffusion) and is under construction: see the [spec](https://github.com/tedliou/StreamTurbo/issues/2) for the roadmap.

StreamTurbo 是給 TouchDesigner 使用的即時影像生成 Runtime，只支援 Windows。它從 NDI 或 Spout 接收影像，在 NVIDIA 顯示卡上用 sd-turbo 單步重新生成每一格，再經由 NDI 或 Spout 送回去。

> [!NOTE]
> 開發中。目前完成的是 M1：用 TOML 設定檔啟動，經 NDI 或 Spout 收送影像並即時生成。Web Panel 等後續功能的進度請見 [spec #2](https://github.com/tedliou/StreamTurbo/issues/2)。

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
5. 執行 `streamturbo run`，用 Glass Preset 開始生成（NDI 收、NDI 送）。第一次執行會下載約 2.3 GB 的模型權重到 `models\`。

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
.venv\Scripts\streamturbo run --settings my.toml
.venv\Scripts\streamturbo run --list-sources
```

不加參數時使用 Glass Preset，經 NDI 收送；`--settings` 指定設定檔；`--list-sources` 列出目前看得到的 NDI 和 Spout 來源後結束。

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

已知限制：Spout 沒有開啟 frame counting 時，StreamTurbo 無法分辨畫面是否更新。這時把 TouchDesigner 的 Spout Out 設為 inactive，狀態仍會顯示 `live`；刪除 Spout Out TOP 才會變成 `lost`。frame counting 是 Spout 的全系統設定（SpoutSettings 工具），StreamTurbo 不會改動它。

## 疑難排解

| 狀況 | 處理方式 |
|---|---|
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

設計文件：[GLOSSARY.md](GLOSSARY.md)、[docs/adr/](docs/adr/)。

## 授權

- 程式碼採用 [Apache-2.0](LICENSE)，源自 StreamDiffusion，詳見 [NOTICE](NOTICE)。
- sd-turbo 模型權重另採 Stability AI Community License，商業使用須遵守該授權條款。本專案本身以非商業用途開發。
- NDI® 是 Vizrt NDI AB 的註冊商標，詳見 [ndi.video](https://ndi.video)。
