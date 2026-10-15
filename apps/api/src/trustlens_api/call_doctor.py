"""Compatibility command for older operator scripts. Implementation: modules.calling.doctor."""
import runpy

if __name__ == "__main__":
    runpy.run_module("trustlens_api.modules.calling.doctor", run_name="__main__")
