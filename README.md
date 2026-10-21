# StreamTurbo

> **English summary.** StreamTurbo is a Windows-only, real-time image-to-image Runtime for TouchDesigner. It receives video over NDI or Spout, regenerates every frame with a single sd-turbo step on an NVIDIA GPU, and sends the result back over NDI or Spout. Clone the repository and double-click `start.cmd`. It is a non-commercial, independent rewrite of [StreamDiffusion](https://github.com/cumulo-autumn/StreamDiffusion) and is under construction: see the [spec](https://github.com/tedliou/StreamTurbo/issues/2) for the roadmap.

StreamTurbo 是給 TouchDesigner 使用的即時影像生成 Runtime，只支援 Windows。它從 NDI 或 Spout 接收影像，在 NVIDIA 顯示卡上用 sd-turbo 單步重新生成每一格，再經由 NDI 或 Spout 送回去。

> [!NOTE]
> 開發中。目前完成的是 M0：專案骨架、啟動器和 `doctor`。生成功能從 M1 開始，進度請見 [spec #2](https://github.com/tedliou/StreamTurbo/issues/2)。

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
2. 找不到 uv 時，把 uv 安裝到 `cache\bin`。
3. 依照 lockfile 同步 Python 3.12 和所有套件（含 CUDA runtime）。第一次執行會下載數 GB。
4. 執行 `streamturbo doctor` 檢查環境。

所有下載都放在專案資料夾內（`cache\`、`models\`、`.venv\`），刪除資料夾即可完整移除。

## `streamturbo doctor`

回報顯示卡名稱、算力、VRAM、驅動程式版本、目前與預設的功率上限、torch 與 CUDA 版本，以及 NDI 和 Spout 是否可用。環境有問題時結束代碼為 1。

```bat
.venv\Scripts\streamturbo doctor
```

## TouchDesigner 連接

M1 完成後補上。

## 疑難排解

| 狀況 | 處理方式 |
|---|---|
| 顯示找不到 NVIDIA 驅動程式 | 從 [NVIDIA 官網](https://www.nvidia.com/Download/index.aspx) 安裝 580 以上的驅動程式 |
| uv 安裝失敗 | 確認網路連線，或手動安裝 [uv](https://docs.astral.sh/uv/) 後重新執行 |
| `doctor` 顯示 NOT READY | 依照 PROBLEM 那幾行的說明處理 |

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
- 僅供非商業用途。sd-turbo 權重採用 Stability AI Community License。
- NDI® 是 Vizrt NDI AB 的註冊商標，詳見 [ndi.video](https://ndi.video)。
