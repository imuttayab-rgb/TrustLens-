"""Compatibility command for older operator scripts. Implementation: modules.photos.backfill."""
import runpy

if __name__ == "__main__":
    runpy.run_module("trustlens_api.modules.photos.backfill", run_name="__main__")
