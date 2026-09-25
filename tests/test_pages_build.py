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

    assert "GitHub Pages browser edition" in index_html
    assert "pyodide.js" in index_html
    assert "Action failed." in index_html
    assert "Architecture sizing for Veeam backup and recovery." in index_html
    assert "Protection architecture builder" in index_html
    assert "YAML and API project definition" in index_html
    assert "Advanced sizing overrides" in index_html
    assert "Proxmox VE" in index_html
    assert "Veeam Software Appliance" in index_html
    assert "Veeam Infrastructure Appliance" in index_html
    assert 'id="proxy-deployment-mode"' in index_html
    assert 'data-platforms="vmware"' in index_html
    assert 'data-workload-scope="vm"' in index_html
    assert "Architecture Snapshot" in index_html
    assert (output_dir / "assets" / "app.css").exists()
    assert (output_dir / "assets" / "app.js").exists()
    assert (output_dir / "assets" / fake_wheel.name).exists()
    assert "veeam-designer-print-frame" in app_js
    assert "platform_concurrent_tasks" in app_js
    assert "deployment_mode" in app_js
    assert "proxy_deployment_mode" in app_js
    assert "syncContextVisibility" in app_js
    assert "renderHumanOutput" in app_js
    assert "frame.srcdoc = markup;" in app_js
    assert 'window.open("", "_blank"' not in app_js
