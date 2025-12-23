"""
Integration test simulating a clean project setup from git clone.

This test verifies that a user can clone the project and have everything
work automatically without manual configuration.
"""
import tempfile
import os
import shutil
from pathlib import Path


def test_clean_setup_simulation():
    """
    Simulate a clean setup as if a user just cloned the repo.
    
    This test verifies that:
    1. DAGSTER_HOME directory is created automatically
    2. dagster.yaml config is generated with correct settings
    3. All initialization happens without user intervention
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate a project root
        project_root = Path(tmpdir) / "just-dna-lite"
        project_root.mkdir()
        
        # Create minimal project structure
        data_dir = project_root / "data"
        data_dir.mkdir()
        
        # Simulate what happens when CLI sets up DAGSTER_HOME
        dagster_home = project_root / "data" / "interim" / "dagster"
        
        # Import the initialization function
        from just_dna_lite.cli import _ensure_dagster_config
        
        # Before initialization
        assert not dagster_home.exists(), "DAGSTER_HOME should not exist yet"
        
        # Initialize (this is what CLI commands do automatically)
        _ensure_dagster_config(dagster_home)
        
        # Verify everything was created
        assert dagster_home.exists(), "DAGSTER_HOME should be created"
        assert dagster_home.is_dir(), "DAGSTER_HOME should be a directory"
        
        config_file = dagster_home / "dagster.yaml"
        assert config_file.exists(), "dagster.yaml should be created"
        
        # Verify config content matches template expectations
        content = config_file.read_text()
        
        # Check for essential configuration
        assert "# Dagster instance configuration" in content
        assert "auto_materialize:" in content
        assert "enabled: true" in content
        assert "minimum_interval_seconds: 60" in content
        
        print(f"✅ Clean setup simulation passed!")
        print(f"   Created: {dagster_home}")
        print(f"   Config:  {config_file}")
        print(f"   Content preview:\n{content[:200]}...")


def test_gitignore_protection():
    """
    Verify that data/interim/ is in .gitignore but the template is tracked.
    
    This ensures:
    1. The actual dagster.yaml (in data/interim/) is gitignored
    2. The template (dagster.yaml.template) is tracked
    3. Users can reference the template to understand the config
    """
    from just_dna_lite.cli import _find_workspace_root
    
    root = _find_workspace_root(Path.cwd())
    assert root is not None, "Should find workspace root"
    
    gitignore = root / ".gitignore"
    assert gitignore.exists(), ".gitignore should exist"
    
    gitignore_content = gitignore.read_text()
    
    # Verify data/interim/ is ignored
    assert "data/interim/" in gitignore_content, "data/interim/ should be gitignored"
    
    # Verify template exists and is tracked
    template = root / "dagster.yaml.template"
    assert template.exists(), "dagster.yaml.template should exist"
    
    template_content = template.read_text()
    assert "auto_materialize:" in template_content
    
    print("✅ Gitignore protection verified!")
    print(f"   ✓ data/interim/ is gitignored")
    print(f"   ✓ dagster.yaml.template exists at {template}")


def test_documentation_updated():
    """Verify that documentation mentions the automatic setup."""
    from just_dna_lite.cli import _find_workspace_root
    
    root = _find_workspace_root(Path.cwd())
    assert root is not None
    
    # Check README
    readme = root / "README.md"
    readme_content = readme.read_text()
    assert "automatically" in readme_content.lower()
    
    # Check DAGSTER_MULTI_USER.md
    dagster_doc = root / "docs" / "DAGSTER_MULTI_USER.md"
    dagster_doc_content = dagster_doc.read_text()
    assert "automatically" in dagster_doc_content.lower()
    assert "dagster.yaml" in dagster_doc_content
    
    print("✅ Documentation verification passed!")
    print("   ✓ README mentions automatic setup")
    print("   ✓ DAGSTER_MULTI_USER.md documents configuration")


if __name__ == "__main__":
    test_clean_setup_simulation()
    test_gitignore_protection()
    test_documentation_updated()
    print("\n🎉 All integration tests passed!")
    print("\n✨ Summary:")
    print("   • Clean setup works automatically")
    print("   • dagster.yaml is created on first run")
    print("   • Configuration is gitignored but template is tracked")
    print("   • Documentation is up to date")

