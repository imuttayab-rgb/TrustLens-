"""Compatibility command for older operator scripts. Implementation: modules.messaging.archive."""
import runpy

if __name__ == "__main__":
    runpy.run_module("trustlens_api.modules.messaging.archive", run_name="__main__")
