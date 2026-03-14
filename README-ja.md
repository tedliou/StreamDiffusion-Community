# StreamDiffusion

[English](./README.md) | [日本語](./README-ja.md) | [한국어](./README-ko.md)

## 概要

このリポジトリは現在、StreamDiffusion Python パッケージのコアソースワークスペースとして整理されています。

安定した `uv` ベースの開発環境に集中するため、今回の変更では `demo/`、`examples/`、およびパッケージ公開フローを一旦削除しています。将来の大きなリファクタで、より整理された形で再導入する予定です。

## 現在の範囲

- `src/streamdiffusion/` 配下のコア Python パッケージ
- コアワークスペース向けのルート `Dockerfile`
- OpenSpec ベースのコラボレーション関連ファイル

今回の範囲外:

- 同梱デモや examples
- PyPI/TestPyPI 公開
- GPU 依存を含むフル実行環境のデフォルト提供

## 必要条件

- Linux または WSL2
- Python 3.10 以上
- `uv`

`uv` が未導入の場合、Ubuntu/WSL2 では次のインストーラが使えます。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## セットアップ

```bash
git clone https://github.com/cumulo-autumn/StreamDiffusion.git
cd StreamDiffusion
uv sync
uv run python -c "import streamdiffusion; print('streamdiffusion import OK')"
```

このリポジトリの現在の基準は、`uv sync` が成功し、パッケージを import できることです。今回の変更では、推論まで含めた実行環境は保証しません。

## 依存関係に関する注意

- `torch` と `xformers` は、この安定化フェーズではデフォルトの `uv sync` に含めていません。
- ただし、どちらも今後のリファクタでメインワークフローへ戻すべき必須依存です。
- `pyproject.toml` には follow-up 用の optional extras を残していますが、今回のベースライン検証には含めていません。

## Docker

ルート `Dockerfile` も同じ軽量セットアップを使います。

```bash
docker build -t streamdiffusion-core .
docker run --rm streamdiffusion-core
```

## 現在の状態

- このリポジトリは現時点ではエンドユーザー向けではなく、開発者向けです。
- リリース自動化は今回の範囲から意図的に外しています。
- TensorRT などの加速系コードは残っていますが、完全なセットアップは次の大きなリファクタで扱います。
