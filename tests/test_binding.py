import os

import pytest

from easy_context_mcp.binding import BindingError, project_id_for, resolve_project


def svc(header=None, arg=None):
    return resolve_project(header_root=header, arg_root=arg, service_mode=True)


def test_header_binds(tmp_path):
    p = svc(header=str(tmp_path))
    assert p.root == os.path.realpath(tmp_path)


def test_arg_fallback(tmp_path):
    assert svc(arg=str(tmp_path)).root == os.path.realpath(tmp_path)


def test_header_and_arg_equal_ok(tmp_path):
    assert svc(header=str(tmp_path), arg=str(tmp_path) + "/").root == os.path.realpath(tmp_path)


def test_conflict_names_both(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    with pytest.raises(BindingError) as e:
        svc(header=str(a), arg=str(b))
    assert str(a) in str(e.value) and str(b) in str(e.value)


def test_neither_names_both_options():
    with pytest.raises(BindingError) as e:
        svc()
    assert "X-Easy-Context-Root" in str(e.value) and "root" in str(e.value)


def test_stdio_defaults_to_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CONTEXT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    p = resolve_project(header_root=None, arg_root=None, service_mode=False)
    assert p.root == os.path.realpath(tmp_path)


def test_stdio_env_overrides_cwd_and_arg_overrides_env(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("EASY_CONTEXT_ROOT", str(a))
    monkeypatch.chdir(tmp_path)
    assert resolve_project(header_root=None, arg_root=None, service_mode=False).root == str(a)
    assert resolve_project(header_root=None, arg_root=str(b), service_mode=False).root == str(b)


def test_stdio_ignores_header(tmp_path, monkeypatch):
    monkeypatch.delenv("EASY_CONTEXT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    p = resolve_project(header_root="/nonexistent", arg_root=None, service_mode=False)
    assert p.root == os.path.realpath(tmp_path)


def test_project_id_stable_across_symlink_and_slash(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    ids = {
        svc(header=str(real)).project_id,
        svc(header=str(link)).project_id,
        svc(header=str(real) + "/").project_id,
        svc(header=str(real) + "/../real").project_id,
    }
    assert len(ids) == 1


def test_project_id_differs_for_different_roots(tmp_path):
    a, b = tmp_path / "x" / "app", tmp_path / "y" / "app"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    assert svc(header=str(a)).project_id != svc(header=str(b)).project_id


def test_project_id_sanitizes_basename():
    assert project_id_for("/tmp/we ird/na;me").startswith("na-me-")


def test_bad_roots_error_and_create_nothing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(home))
    f = tmp_path / "file.txt"
    f.write_text("x")
    for bad in (str(tmp_path / "missing"), str(f), "relative/path"):
        with pytest.raises(BindingError):
            svc(header=bad)
    assert not home.exists()
