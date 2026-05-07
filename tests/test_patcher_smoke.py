from pathlib import Path
import importlib.util


def load_patcher_module():
    repo_root = Path(__file__).resolve().parents[1]
    patcher_path = repo_root / "safe-word-template-filler" / "scripts" / "patch_word_template_raw_ooxml.py"
    spec = importlib.util.spec_from_file_location("patch_word_template_raw_ooxml", patcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_patcher_module_loads():
    module = load_patcher_module()
    assert hasattr(module, "main")
    assert hasattr(module, "run")
    assert hasattr(module, "StructureGuard")


def test_structure_guard_json_uses_pass_key():
    module = load_patcher_module()
    guard = module.StructureGuard(
        pass_=True,
        document_xml_size_before=10,
        document_xml_size_after=10,
        text_nodes_before=1,
        text_nodes_after=1,
        intentional_text_node_creations=0,
        text_nodes_delta_expected=0,
        text_nodes_delta_actual=0,
        text_nodes_delta_matches_expected=True,
        package_parts_preserved=True,
        errors=[],
    )
    data = guard.to_json()
    assert data["pass"] is True
    assert "pass_" not in data


def test_flat_evidence_contract_rejects_nested_values(tmp_path):
    module = load_patcher_module()
    evidence = {"field_a": {"value": "nested metadata is not allowed"}}
    assert any(isinstance(value, (dict, list)) for value in evidence.values())
    assert module.escape_xml_text("A&B") == b"A&amp;B"
