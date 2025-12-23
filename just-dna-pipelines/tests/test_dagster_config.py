"""
Test that Dagster configuration is properly initialized on clean setup.

This test verifies that the automatic configuration initialization works
correctly when setting up the project for the first time.
"""
from pathlib import Path
import tempfile
import os
import shutil


def test_dagster_config_initialization():
    """Test that dagster.yaml is created automatically on first setup."""
    from just_dna_lite.cli import _ensure_dagster_config
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        dagster_home = Path(tmpdir) / "test_dagster_home"
        
        # Verify config doesn't exist yet
        config_file = dagster_home / "dagster.yaml"
        assert not config_file.exists(), "Config should not exist initially"
        
        # Call the initialization function
        _ensure_dagster_config(dagster_home)
        
        # Verify config was created
        assert config_file.exists(), "Config should be created"
        
        # Verify config content
        content = config_file.read_text()
        assert "auto_materialize:" in content
        assert "enabled: true" in content
        assert "minimum_interval_seconds: 60" in content
        
        print("✅ Dagster config initialization test passed!")


def test_dagster_config_not_overwritten():
    """Test that existing dagster.yaml is not overwritten."""
    from just_dna_lite.cli import _ensure_dagster_config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        dagster_home = Path(tmpdir) / "test_dagster_home"
        dagster_home.mkdir(parents=True)
        
        config_file = dagster_home / "dagster.yaml"
        
        # Create a custom config
        custom_content = "# Custom configuration\nauto_materialize:\n  enabled: false\n"
        config_file.write_text(custom_content)
        
        # Call initialization again
        _ensure_dagster_config(dagster_home)
        
        # Verify custom config was not overwritten
        content = config_file.read_text()
        assert content == custom_content, "Existing config should not be overwritten"
        assert "enabled: false" in content
        
        print("✅ Config preservation test passed!")


def test_cli_dagster_setup():
    """Test that CLI commands properly initialize DAGSTER_HOME."""
    from just_dna_lite.cli import _find_workspace_root, _ensure_dagster_config
    
    # This test uses the actual workspace root
    root = _find_workspace_root(Path.cwd())
    assert root is not None, "Should find workspace root"
    
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    
    # Test that initialization works
    _ensure_dagster_config(dagster_home_path)
    
    config_file = dagster_home_path / "dagster.yaml"
    assert config_file.exists(), "Config should exist in actual workspace"
    
    content = config_file.read_text()
    assert "auto_materialize:" in content
    
    print(f"✅ CLI setup test passed! Config at: {config_file}")


if __name__ == "__main__":
    test_dagster_config_initialization()
    test_dagster_config_not_overwritten()
    test_cli_dagster_setup()
    print("\n🎉 All Dagster configuration tests passed!")

