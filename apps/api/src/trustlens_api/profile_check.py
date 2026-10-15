"""Compatibility command for older operator scripts. Implementation: modules.profiles.check."""
import runpy

if __name__ == "__main__":
    runpy.run_module("trustlens_api.modules.profiles.check", run_name="__main__")
