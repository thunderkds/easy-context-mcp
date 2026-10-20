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


def _repo(tmp_path, git_is_file=False):
    repo = tmp_path / "repo"
    sub = repo / "pkg" / "inner"
    sub.mkdir(parents=True)
    if git_is_file:
        (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/repo\n")
    else:
        (repo / ".git").mkdir()
    return repo, sub


def test_subdir_of_git_repo_binds_repo_root(tmp_path):
    repo, sub = _repo(tmp_path)
    assert svc(header=str(sub)).root == os.path.realpath(repo)


def test_subdir_of_worktree_binds_worktree_root_not_main(tmp_path):
    main, _ = _repo(tmp_path / "main_checkout")
    wt, sub = _repo(tmp_path / "wt", git_is_file=True)
    assert svc(header=str(sub)).root == os.path.realpath(wt)
    assert svc(header=str(sub)).root != os.path.realpath(main)


def test_header_subdir_and_arg_repo_root_no_conflict(tmp_path):
    repo, sub = _repo(tmp_path)
    assert svc(header=str(sub), arg=str(repo)).root == os.path.realpath(repo)


def test_non_git_dir_unchanged(tmp_path):
    d = tmp_path / "plain" / "deep"
    d.mkdir(parents=True)
    assert svc(header=str(d)).root == os.path.realpath(d)


def test_subdir_project_id_equals_repo_root_id(tmp_path):
    repo, sub = _repo(tmp_path)
    assert svc(header=str(sub)).project_id == svc(header=str(repo)).project_id


def test_stdio_cwd_and_env_walk_up(tmp_path, monkeypatch):
    repo, sub = _repo(tmp_path)
    monkeypatch.delenv("EASY_CONTEXT_ROOT", raising=False)
    monkeypatch.chdir(sub)
    stdio = resolve_project(header_root=None, arg_root=None, service_mode=False)
    assert stdio.root == os.path.realpath(repo)
    monkeypatch.setenv("EASY_CONTEXT_ROOT", str(sub))
    assert resolve_project(header_root=None, arg_root=None, service_mode=False).root == stdio.root


def test_walk_up_never_reaches_home(tmp_path, monkeypatch):
    home = tmp_path / "home" / "me"
    proj = home / "code" / "proj"
    proj.mkdir(parents=True)
    (home / ".git").mkdir()  # dotfiles repo at ~/.git
    monkeypatch.setenv("HOME", str(home))
    assert svc(header=str(proj)).root == os.path.realpath(proj)


def test_walk_up_never_reaches_home_ancestor(tmp_path, monkeypatch):
    home = tmp_path / "home" / "me"
    proj = home / "proj"
    proj.mkdir(parents=True)
    (tmp_path / ".git").mkdir()  # repo above $HOME
    monkeypatch.setenv("HOME", str(home))
    assert svc(header=str(proj)).root == os.path.realpath(proj)


def test_home_given_exactly_binds_home(tmp_path, monkeypatch):
    home = tmp_path / "home" / "me"
    home.mkdir(parents=True)
    (home / ".git").mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert svc(header=str(home)).root == os.path.realpath(home)


def test_repo_under_home_still_walks_up(tmp_path, monkeypatch):
    home = tmp_path / "home" / "me"
    repo = home / "repo"
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert svc(header=str(sub)).root == os.path.realpath(repo)


# --- workspace ceiling (FR-018/FR-019, HUN-13) ---


def _ws(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "repo" / "sub").mkdir(parents=True)
    (ws / "repo" / ".git").mkdir()
    monkeypatch.setenv("EASY_CONTEXT_WORKSPACE", str(ws))
    return ws


def test_workspace_binds_repo_inside(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    assert svc(header=str(ws / "repo" / "sub")).root == str(ws / "repo")


def test_workspace_rejects_root_outside(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(BindingError) as e:
        svc(header=str(other))
    assert "outside the workspace" in str(e.value) and "EASY_CONTEXT_WORKSPACE" in str(e.value)


def test_workspace_rejects_sibling_with_shared_prefix(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    sneaky = tmp_path / "ws-evil"
    sneaky.mkdir()
    with pytest.raises(BindingError):
        svc(arg=str(sneaky))


def test_workspace_rejects_symlink_escape(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (ws / "link").symlink_to(outside)
    with pytest.raises(BindingError):
        svc(header=str(ws / "link"))


def test_git_walk_stops_at_workspace(tmp_path, monkeypatch):
    # a .git ABOVE the workspace must never be returned
    (tmp_path / ".git").mkdir()
    ws = tmp_path / "ws"
    (ws / "plain").mkdir(parents=True)
    monkeypatch.setenv("EASY_CONTEXT_WORKSPACE", str(ws))
    assert svc(header=str(ws / "plain")).root == str(ws / "plain")


def test_workspace_itself_may_be_a_root(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    assert svc(header=str(ws)).root == str(ws)
