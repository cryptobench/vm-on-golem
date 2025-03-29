import pytest

# Autouse fixture to patch settings validation before any test runs
@pytest.fixture(autouse=True, scope='function') # Match monkeypatch scope
def patch_settings_validation(monkeypatch: pytest.MonkeyPatch):
    """
    Patches problematic validations in Settings model that depend on
    external environment (like multipass binary) before tests are collected.
    """
    try:
        # Attempt to import the class to be patched
        from provider.config import Settings
        # Patch the multipass validation method
        monkeypatch.setattr(Settings, "_validate_multipass_path", lambda *args, **kwargs: True, raising=False)
        # Patch other validations if needed, e.g., port checks if they cause issues
        # monkeypatch.setattr(Settings, "_validate_ports", lambda *args, **kwargs: True, raising=False)
        print("Successfully patched Settings validations in conftest.py") # Debug print
    except ImportError:
        # Handle case where the module/class might not exist yet or path is wrong
        print("Warning: Could not import provider.config.Settings in conftest.py for patching.")
    except AttributeError:
        # Handle case where the method to patch doesn't exist
        print("Warning: Could not find _validate_multipass_path on Settings class for patching.")

# Add other session-wide fixtures here if needed
