"""docs/api/openapi.yaml must not repeat a key: YAML silently keeps only the last copy."""

from pathlib import Path

import pytest
import yaml

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs/api/openapi.yaml"


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping_without_duplicates(loader, node, deep=False):
    keys = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in keys:
            raise ValueError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        keys.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_without_duplicates
)


def test_openapi_spec_has_no_duplicate_keys():
    yaml.load(SPEC_PATH.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)


def test_duplicate_keys_are_detected():
    with pytest.raises(ValueError, match="duplicate key 'a'"):
        yaml.load("a: 1\nb: 2\na: 3\n", Loader=_UniqueKeyLoader)
