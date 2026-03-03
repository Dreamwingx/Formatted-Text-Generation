import os
import logging

import pytest

from src.modules.preprocess import pipeline


def _make_subdir_with_full(output, name):
    d = output / name
    d.mkdir()
    (d / "full.md").write_text("dummy")


def test_pipeline_no_full(tmp_path, caplog):
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    output_dir.mkdir()
    work_dir.mkdir()
    caplog.set_level(logging.WARNING)

    pipeline(str(output_dir), str(work_dir))

    assert "未找到任何full.md" in caplog.text
    assert not (output_dir / "filecollection_result.txt").exists()


def test_pipeline_single_full(tmp_path, caplog):
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    output_dir.mkdir()
    work_dir.mkdir()
    _make_subdir_with_full(output_dir, "a")
    caplog.set_level(logging.INFO)

    pipeline(str(output_dir), str(work_dir))

    assert "选择文件" in caplog.text
    assert "a" in caplog.text
    result = (output_dir / "filecollection_result.txt").read_text()
    assert result.strip() == "a"

    # file should remain unchanged because no headings to align
    assert (output_dir / "a" / "full.md").read_text() == "dummy"


def test_pipeline_multiple_full(tmp_path, caplog):
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    output_dir.mkdir()
    work_dir.mkdir()
    _make_subdir_with_full(output_dir, "a")
    _make_subdir_with_full(output_dir, "b")
    caplog.set_level(logging.WARNING)

    pipeline(str(output_dir), str(work_dir))

    assert "仅处理第一个" in caplog.text
    result = (output_dir / "filecollection_result.txt").read_text()
    assert result.strip() == "a"


def test_pipeline_title_alignment(tmp_path, caplog):
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"
    output_dir.mkdir()
    work_dir.mkdir()
    d = output_dir / "x"
    d.mkdir()
    # create a misformatted heading
    (d / "full.md").write_text("#1.1测试标题\n# 2测试\n")
    caplog.set_level(logging.INFO)

    pipeline(str(output_dir), str(work_dir))

    # after running, the file should have normalized spaces
    contents = (d / "full.md").read_text().splitlines()
    assert contents[0] == "# 1.1 测试标题"
    assert contents[1] == "# 2 测试"
