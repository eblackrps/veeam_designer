from tools import build_pages
from veeam_designer import __version__


def test_build_pages_outputs_static_site(tmp_path, monkeypatch):
    fake_wheel = tmp_path / f"veeam_designer-{__version__}-py3-none-any.whl"
    fake_wheel.write_bytes(b"wheel")
    monkeypatch.setattr(build_pages, "find_release_wheel", lambda: fake_wheel)

    output_dir = tmp_path / "site"
    build_pages.build_pages(output_dir)

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    app_js = (output_dir / "assets" / "app.js").read_text(encoding="utf-8")

    assert "Browser edition" in index_html
    assert "pyodide.js" in index_html
    assert "Calculation error." in index_html
    assert "Veeam infrastructure sizing." in index_html
    assert "Model backup capacity, infrastructure requirements, WAN demand, and storage cost" in index_html
    assert "Design inputs" in index_html
    assert "YAML / API input" in index_html
    assert "Advanced parameters" in index_html
    assert "Proxmox VE" in index_html
    assert "Veeam Software Appliance" in index_html
    assert "Veeam Infrastructure Appliance" in index_html
    assert 'id="proxy-deployment-mode"' in index_html
    assert 'data-platforms="vmware"' in index_html
    assert 'data-workload-scope="vm"' in index_html
    assert "Infrastructure Summary" in index_html
    assert '<svg viewBox="0 0 24 24"' in index_html
    assert 'id="runtime-status"' not in index_html
    assert "Browser engine ready." not in app_js
    assert (output_dir / "assets" / "app.css").exists()
    assert (output_dir / "assets" / "app.js").exists()
    assert (output_dir / "assets" / fake_wheel.name).exists()
    assert "veeam-designer-print-frame" not in app_js
    assert 'window.open("about:blank", "_blank")' in app_js
    assert 'fetch("/export/report"' in app_js
    assert "renderResultBundle(null)" in app_js
    assert "Print / Save PDF" in app_js
    assert "frame.srcdoc = markup;" not in app_js
    assert "platform_concurrent_tasks" in app_js
    assert "deployment_mode" in app_js
    assert "proxy_deployment_mode" in app_js
    assert "capacity_tier_fraction" not in app_js
    assert "capacity_tier_operational_restore_days" in app_js
    assert "capacity_tier_policy" in app_js
    assert "capacity_tier_immutable" in app_js
    assert "object_cost_usd_per_tb_month" in app_js
    assert "onprem_cost_usd_per_tb_year" in app_js
    assert "Modeled Storage Cost / Year" in app_js
    assert "Operational Restore Window" in index_html
    assert "Modeled Move Fraction" not in index_html
    assert "Break-even" not in app_js
    assert "syncContextVisibility" in app_js
    assert "renderHumanOutput" in app_js
    assert 'window.open("", "_blank"' not in app_js
