# StreamDiffusion

[English](./README.md) | [日本語](./README-ja.md) | [한국어](./README-ko.md)

## 개요

이 저장소는 현재 StreamDiffusion Python 패키지의 코어 소스 워크스페이스로 정리되어 있습니다.

지금은 안정적인 `uv` 기반 개발 환경에 집중하기 위해 `demo/`, `examples/`, 패키지 배포 자동화를 잠시 제거했습니다. 이후의 큰 리팩터링에서 더 정리된 형태로 다시 추가할 예정입니다.

## 현재 범위

- `src/streamdiffusion/` 아래의 코어 Python 패키지
- 코어 워크스페이스용 루트 `Dockerfile`
- OpenSpec 기반 협업 관련 파일

이번 범위에 포함되지 않는 것:

- 내장 demo 및 examples
- PyPI/TestPyPI 배포
- GPU 의존성을 포함한 전체 실행 환경의 기본 제공

## 요구 사항

- Linux 또는 WSL2
- Python 3.10 이상
- `uv`

`uv` 가 아직 없다면 Ubuntu/WSL2 에서는 다음 설치 스크립트를 사용할 수 있습니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 설정

```bash
git clone https://github.com/cumulo-autumn/StreamDiffusion.git
cd StreamDiffusion
uv sync
uv run python -c "import streamdiffusion; print('streamdiffusion import OK')"
```

현재 이 저장소의 기준은 `uv sync` 가 성공하고 패키지를 import 할 수 있는지입니다. 이번 변경에서는 추론까지 가능한 전체 실행 환경을 보장하지 않습니다.

## 의존성 메모

- `torch` 와 `xformers` 는 이번 안정화 단계에서 기본 `uv sync` 환경에 포함되지 않습니다.
- 하지만 두 패키지는 이후 리팩터링에서 메인 워크플로에 반드시 다시 포함되어야 하는 필수 의존성입니다.
- `pyproject.toml` 에 optional extras 는 남겨 두지만, 이번 기본 검증 범위에는 포함하지 않습니다.

## Docker

루트 `Dockerfile` 도 같은 경량 설정 경로를 사용합니다.

```bash
docker build -t streamdiffusion-core .
docker run --rm streamdiffusion-core
```

## 현재 상태

- 이 저장소는 현재 최종 사용자용보다는 개발자용입니다.
- 릴리스 자동화는 이번 범위에서 의도적으로 제거했습니다.
- TensorRT 같은 가속화 관련 코드는 남아 있지만, 전체 설정 흐름은 다음 큰 리팩터링에서 다룰 예정입니다.
