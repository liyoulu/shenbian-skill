# -*- coding: utf-8 -*-
"""marker_probe 测试基线：_env 解析与工具参数校验。

运行：python -m pytest tests/ -v   （在仓库根目录，用任何装了 pytest 的 Python）
CI 里在没有深变的机器上跑：通过 DFL_ROOT 指向 fixtures 里的假仓库骨架。
"""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(os.path.dirname(HERE), 'tools', 'marker_probe')
sys.path.insert(0, MP)


@pytest.fixture()
def fake_root(tmp_path):
    """假深变仓库骨架：入口 + 最小 onnx 集，供 _env/selfcheck 用。"""
    (tmp_path / 'main.py').write_text('# fake', encoding='utf-8')
    onnx = tmp_path / 'modelhub' / 'onnx'
    for rel in (r'BlazeFace\blaze.onnx', r'InsightFace2d106\InsightFace2D106.onnx',
                r'InsightFace3D68\1k3d68.onnx', r'FAN\2DFAN.onnx', r'FAN\3DFAN.onnx'):
        p = onnx / os.path.join(*rel.split('\\'))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'fake-onnx')
    return tmp_path


def test_env_resolves_root(monkeypatch, fake_root):
    monkeypatch.setenv('DFL_ROOT', str(fake_root))
    monkeypatch.setenv('SHENBIAN_STRICT_ROOT', '1')
    import importlib
    import _env
    importlib.reload(_env)
    assert _env.ROOT == str(fake_root)
    assert os.path.isfile(os.path.join(_env.ROOT, 'main.py'))


def test_env_rejects_bad_root(monkeypatch, fake_root):
    bad = fake_root / 'not_a_repo'
    bad.mkdir()
    monkeypatch.setenv('DFL_ROOT', str(bad))
    monkeypatch.setenv('SHENBIAN_STRICT_ROOT', '1')
    import importlib
    import _env
    with pytest.raises(SystemExit):
        importlib.reload(_env)


def test_selfcheck_passes_with_fake_root(monkeypatch, fake_root):
    monkeypatch.setenv('DFL_ROOT', str(fake_root))
    monkeypatch.setenv('SHENBIAN_STRICT_ROOT', '1')
    import importlib
    import _env
    importlib.reload(_env)
    # onnxruntime 探测在无包环境会 FAIL —— 本测试只验证行数与格式
    ok, lines = _env.selfcheck()
    assert isinstance(lines, list) and len(lines) >= 5
    assert any('DFL_ROOT' in ln for ln in lines)


@pytest.mark.parametrize('tool', ['make_contact_sheet.py', 'video_landmarker_test.py', 'video_segment_test.py'])
def test_tools_have_check_flag(monkeypatch, fake_root, tool):
    """--check 应正常退出（假根目录下 onnx 齐全；onnxruntime 缺失允许 FAIL → exit 2）。"""
    monkeypatch.setenv('DFL_ROOT', str(fake_root))
    r = subprocess.run([sys.executable, os.path.join(MP, tool), '--check'],
                       capture_output=True, text=True, timeout=120,
                       cwd=MP)
    assert r.returncode in (0, 2), f'{tool}: {r.stdout} {r.stderr}'
    assert 'DFL_ROOT' in r.stdout


def test_doctor_json_schema(monkeypatch, fake_root):
    monkeypatch.setenv('DFL_ROOT', str(fake_root))
    monkeypatch.setenv('SHENBIAN_STRICT_ROOT', '1')
    doctor = os.path.join(os.path.dirname(HERE), 'tools', 'doctor.py')
    r = subprocess.run([sys.executable, doctor, '--json'],
                       capture_output=True, text=True, timeout=180)
    import json
    data = json.loads(r.stdout)
    assert data['root'] == str(fake_root)
    names = {c['name'] for c in data['checks']}
    assert {'dfl_root', 'modelhub_onnx', 'ffmpeg', 'cuda_provider'} <= names
