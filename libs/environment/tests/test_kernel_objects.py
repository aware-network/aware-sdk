from aware_environments.kernel import get_environment


def _function_map(spec):
    return {func.name: func for func in spec.functions}


def test_release_spec_metadata():
    env = get_environment()
    spec = env.objects.get("release")
    assert spec is not None

    funcs = _function_map(spec)
    assert {"bundle", "locks-generate", "publish"}.issubset(funcs.keys())

    bundle_meta = funcs["bundle"].metadata
    assert bundle_meta["selectors"] == ("workspace_root", "repository_root")
    assert bundle_meta["pathspecs"]["creates"] == ["release-bundles"]

    locks_meta = funcs["locks-generate"].metadata
    assert "release-locks" in locks_meta["pathspecs"]["updates"]

    path_ids = {ps.id for ps in spec.pathspecs}
    assert {"release-workspace", "release-bundles", "release-locks"}.issubset(path_ids)


def test_terminal_spec_metadata():
    env = get_environment()
    spec = env.objects.get("terminal")
    assert spec is not None

    funcs = _function_map(spec)
    assert {"create", "bind-provider", "list", "session-resolve"}.issubset(funcs.keys())

    create_meta = funcs["create"].metadata
    selectors = tuple(create_meta["selectors"])
    expected_selector_sets = {
        ("process_slug", "thread_slug", "terminal_slug"),
        ("thread_identifier", "terminal_id"),
    }
    assert selectors in expected_selector_sets
    assert "terminal-descriptor" in create_meta["pathspecs"]["creates"]

    bind_meta = funcs["bind-provider"].metadata
    updates = set(bind_meta["pathspecs"]["updates"])
    expected_updates = {
        "thread-participants-manifest",
        "participants-manifest",
    }
    assert updates.intersection(expected_updates)

    path_ids = {ps.id for ps in spec.pathspecs}
    expected_paths = {
        "terminal-descriptor",
        "terminal-pane-manifest",
        "thread-terminals-dir",
    }
    assert expected_paths.issubset(path_ids)
