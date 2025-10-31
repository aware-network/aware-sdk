import pytest

try:
    from aware_sdk.environment.registry import list_objects
    from aware_cli.objects.registry import list_objects as cli_list_objects
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency bridge
    pytest.skip(f"Missing dependency for registry parity test: {exc}", allow_module_level=True)


def test_object_registry_parity():
    sdk_specs = list_objects()
    cli_specs = cli_list_objects()

    assert [spec.type for spec in sdk_specs] == [spec.type for spec in cli_specs]
    for sdk_spec, cli_spec in zip(sdk_specs, cli_specs, strict=True):
        assert sdk_spec is cli_spec
