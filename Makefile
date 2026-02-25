.PHONY: install install-all dev test lint build publish clean installer homebrew

# --- Installation ---

install:
	pip install -e .

install-all:
	pip install -e ".[all]"

dev:
	pip install -e ".[dev,all]"

# --- Quality ---

test:
	python -m pytest tests/ -v

lint:
	python -m ruff check src/ scripts/ tests/

# --- Build & Publish ---

build: clean
	python -m build

publish: build
	python -m twine upload dist/*

publish-test: build
	python -m twine upload --repository testpypi dist/*

# --- Packaging ---

installer:
	pyinstaller --onefile --name doc-intelligence \
		--add-data "config/config.yaml:config" \
		scripts/cli.py

# --- Homebrew ---

homebrew:
	@echo "Homebrew formula is at packaging/homebrew/doc-intelligence.rb"
	@echo "To install locally: brew install --build-from-source packaging/homebrew/doc-intelligence.rb"

# --- Cleanup ---

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# --- Run ---

scan:
	doc-intelligence scan

dashboard:
	doc-intelligence dashboard

watch:
	doc-intelligence watch

# --- Convenience ---

first-run:
	python -c "from src.onboarding import run_onboarding; run_onboarding()"
