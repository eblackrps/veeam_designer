from tools import build_pages
from veeam_designer import __version__


def test_build_pages_outputs_static_site(tmp_path, monkeypatch):
    fake_wheel = tmp_path / f"veeam_designer-{__version__}-py3-none-any.whl"
    fake_wheel.write_bytes(b"wheel")
    monkeypatch.setattr(build_pages, "find_release_wheel", lambda: fake_wheel)

    output_dir = tmp_path / "site"
    build_pages.build_pages(output_dir)

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "GitHub Pages browser edition" in index_html
    assert "pyodide.js" in index_html
    assert (output_dir / "assets" / "app.css").exists()
    assert (output_dir / "assets" / "app.js").exists()
    assert (output_dir / "assets" / fake_wheel.name).exists()
