"""Seam 2: the committed Web Panel build against a fake-Backend Runtime, driven in a real browser (Edge)."""

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

from streamturbo.backends import BestBackend
from streamturbo.control import Control
from streamturbo.control.web import WebServer
from streamturbo.model_spec import GLASS_PROMPT
from streamturbo.presets import PresetStore
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings, describe
from streamturbo.transports.memory import MemorySink, MemoryTransports, input_frame
from tests.conftest import FakeBackend
from tests.test_runtime import RED, close_to, solid, wait_until


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="msedge")
        except Exception as error:  # every Windows machine has Edge; skip rather than fail elsewhere
            pytest.skip(f"Microsoft Edge is not available: {error}")
        yield browser
        browser.close()


@pytest.fixture
def served(
    small_settings: Settings, net: MemoryTransports, tmp_path: Path
) -> Iterator[tuple[Runtime, MemorySink, str]]:
    net.add_source("cam", repeat_fps=30).push(input_frame(solid(320, 240, RED)))
    sink = net.sink(small_settings.sink)
    runtime = Runtime(small_settings, FakeBackend(), net)
    web = WebServer(Control(runtime, PresetStore(tmp_path / "presets"), net), port=0)
    with runtime:
        web.start()
        try:
            yield runtime, sink, web.url
        finally:
            web.stop()


@pytest.fixture
def page(browser: Browser, served: tuple[Runtime, MemorySink, str]) -> Iterator[Page]:
    page = browser.new_page()
    page.goto(served[2])
    expect(page.get_by_role("status").filter(has_text="Connected")).to_be_visible()
    yield page
    page.close()


def test_the_panel_loads_connects_and_shows_every_setting(page: Page):
    expect(page.locator(".metric", has_text="Source")).to_contain_text("Live")
    expect(page.locator(".metric", has_text="Backend")).to_contain_text("fake")
    for field in describe():
        control = page.locator(f'[data-path="{field["path"]}"]')
        expect(control).to_be_visible()
        expect(control.locator(".badge")).to_have_text(field["class"].capitalize())
    expect(page.get_by_alt_text("Output preview")).to_be_visible()


def test_a_live_setting_changes_output_frames(page: Page, served: tuple[Runtime, MemorySink, str]):
    runtime, sink, _ = served
    strength = page.get_by_label("Strength", exact=True)
    strength.fill("0")
    strength.press("Enter")

    wait_until(lambda: runtime.settings()[0].strength == 0.0)
    version = runtime.settings()[1]
    out = sink.wait_for(lambda f: f.settings_version == version)
    assert close_to(out, RED)  # Strength 0 passes the Input Frame through


def test_a_preset_round_trips(page: Page, served: tuple[Runtime, MemorySink, str]):
    runtime = served[0]
    strength = page.get_by_label("Strength", exact=True)
    strength.fill("0.3")
    strength.press("Enter")
    page.get_by_label("New Preset Name").fill("Show A")
    page.get_by_role("button", name="Save Preset").click()
    row = page.locator('[data-preset="Show A"]')
    expect(row).to_be_visible()

    strength.fill("0.9")
    strength.press("Enter")
    expect(strength).to_have_value("0.9")
    row.get_by_role("button", name="Recall").click()

    expect(strength).to_have_value("0.3")
    wait_until(lambda: runtime.settings()[0].strength == 0.3)


def test_engine_build_progress_shows_until_the_fast_backend_takes_over(
    browser: Browser, small_settings: Settings, net: MemoryTransports, tmp_path: Path
):
    ready = threading.Event()

    def build(progress):
        progress(0.4, "unet")
        ready.wait()
        return FakeBackend(name="tensorrt")

    net.add_source("cam", repeat_fps=30).push(input_frame(solid(320, 240, RED)))
    runtime = Runtime(small_settings, BestBackend(FakeBackend(name="pytorch"), build), net)
    web = WebServer(Control(runtime, PresetStore(tmp_path / "presets"), net), port=0)
    with runtime:
        web.start()
        page = browser.new_page()
        try:
            page.goto(web.url)
            backend = page.locator(".metric", has_text="Backend")
            expect(backend).to_contain_text("pytorch")
            expect(backend).to_contain_text("Building Engines 40%")
            ready.set()
            expect(backend).to_contain_text("tensorrt")
            expect(backend).not_to_contain_text("Building")
        finally:
            page.close()
            web.stop()


def test_the_prompt_blend_adds_weighs_and_removes_prompts(page: Page, served: tuple[Runtime, MemorySink, str]):
    runtime = served[0]

    def blend() -> list[tuple[str, float]]:
        return [(prompt.text, prompt.weight) for prompt in runtime.settings()[0].prompts]

    panel = page.locator('[data-path="prompts"]')
    panel.get_by_role("button", name="Add Prompt").click()
    wait_until(lambda: blend() == [(GLASS_PROMPT, 1.0), ("", 0.0)])  # a new Prompt changes nothing yet
    second = panel.get_by_label("Prompt 2", exact=True)
    second.fill("ice")
    second.press("Control+Enter")
    weight = panel.get_by_label("Prompt 2 Weight", exact=True)
    weight.fill("0.5")
    weight.press("Enter")
    wait_until(lambda: blend() == [(GLASS_PROMPT, 1.0), ("ice", 0.5)])

    panel.get_by_role("button", name="Remove Prompt 1").click()
    wait_until(lambda: blend() == [("ice", 0.5)])
    expect(panel.get_by_role("button", name="Remove Prompt 1")).to_be_disabled()  # a blend keeps one Prompt


def test_the_temporal_coherence_switch_follows_every_control_surface(
    browser: Browser, page: Page, served: tuple[Runtime, MemorySink, str]
):
    runtime = served[0]
    switch = page.get_by_role("switch", name="Temporal Coherence")
    expect(switch).to_be_checked()

    switch.click()
    wait_until(lambda: runtime.settings()[0].temporal_coherence is False)
    expect(switch).not_to_be_checked()

    other = browser.new_page()  # another Control Surface
    other.goto(served[2])
    other.get_by_role("switch", name="Temporal Coherence").click()
    expect(switch).to_be_checked()
    other.close()
