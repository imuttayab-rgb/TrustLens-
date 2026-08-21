# Training entry points.
#
# `make -C apps/ml train` is quoted verbatim in the error the worker raises
# when the classifier artifact is missing, so it has to keep working.

UV ?= uv run

.PHONY: help fetch train compare inspect report clean

help: ## Show these targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

fetch: ## Download the public corpora (EMSCAD, DIFrauD)
	$(UV) trustlens-ml fetch

train: ## Train, evaluate, and export the baseline classifier
	$(UV) trustlens-ml train

train-fast: ## Train without the cross-corpus check or plots
	$(UV) trustlens-ml train --no-cross-corpus --no-plots

compare: ## Trained model vs the keyword heuristic on in-domain listings
	$(UV) trustlens-ml compare

inspect: ## Print the exported artifact's metadata
	$(UV) trustlens-ml inspect

report: fetch train compare ## Everything the report needs, from scratch

clean: ## Remove exported artifacts and generated figures
	rm -rf models/*.joblib reports/*.json reports/figures
