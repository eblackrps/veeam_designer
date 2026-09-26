from __future__ import annotations

# The optional Playwright import intentionally follows pytest.importorskip.
# ruff: noqa: I001

import pytest

try:
    from playwright.sync_api import Browser, expect, sync_playwright  # type: ignore[import-not-found]
except ImportError:
    pytest.skip("Playwright is not installed", allow_module_level=True)

BASE_URL = "http://127.0.0.1:8000/run"


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as manager:
        instance = manager.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture()
def page(browser: Browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)
    page.evaluate("localStorage.clear()")
    page.reload()
    yield page
    context.close()


@pytest.mark.parametrize(
    ("mode", "expected_metric"),
    [
        ("VM Backup", "Repository"),
        ("NAS", "File Proxies"),
        ("Physical", "Required Network"),
        ("Replication", "Replica Storage"),
    ],
)
def test_all_workload_modes_calculate(page, mode: str, expected_metric: str) -> None:
    if mode != "VM Backup":
        page.get_by_role("button", name=mode, exact=True).click()

    with page.expect_navigation():
        page.get_by_role("button", name="Calculate", exact=True).click()

    expect(page.locator("#summary-cards")).to_be_visible()
    expect(page.locator("#summary-cards")).to_contain_text(expected_metric)
    expect(page.locator("#error-alert")).to_be_hidden()


def test_json_csv_and_report_exports(page) -> None:
    with page.expect_navigation():
        page.get_by_role("button", name="Calculate", exact=True).click()

    with page.expect_download() as json_download:
        page.get_by_role("button", name="JSON", exact=True).click()
    assert json_download.value.suggested_filename.endswith(".json")

    with page.expect_download() as csv_download:
        page.get_by_role("button", name="CSV", exact=True).click()
    assert csv_download.value.suggested_filename == "veeam-designer-results.csv"

    with page.expect_popup() as report_popup:
        page.get_by_role("button", name="Report", exact=True).click()
    report = report_popup.value
    report.wait_for_load_state()
    expect(report.locator("body")).to_contain_text("Infrastructure Sizing Report")


def test_mobile_layout_has_no_horizontal_overflow(browser: Browser) -> None:
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(BASE_URL)
    page.evaluate("localStorage.clear()")
    page.reload()

    expect(page.get_by_role("button", name="Calculate", exact=True)).to_be_visible()
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    assert overflow is False

    context.close()
