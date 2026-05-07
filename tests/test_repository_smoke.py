from pathlib import Path


def test_repository_has_readme():
    assert Path("README.md").exists()


def test_safe_word_template_filler_skill_exists():
    assert Path("safe-word-template-filler/SKILL.md").exists()


def test_raw_ooxml_patcher_exists():
    assert Path("safe-word-template-filler/scripts/patch_word_template_raw_ooxml.py").exists()
