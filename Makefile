.PHONY: help install install-dev uninstall clean test lint format run dashboard

PYTHON := python3
PIP := $(PYTHON) -m pip
VENV := .venv
BIN := $(VENV)/bin

help:
	@echo "Captain's Log - Personal Activity Tracking"
	@echo ""
	@echo "Usage:"
	@echo "  make install       Install Captain's Log"
	@echo "  make install-dev   Install with development dependencies"
	@echo "  make uninstall     Uninstall Captain's Log"
	@echo "  make run           Start the daemon in foreground"
	@echo "  make dashboard     Start the web dashboard"
	@echo "  make test          Run tests"
	@echo "  make lint          Run linter"
	@echo "  make format        Format code"
	@echo "  make clean         Remove build artifacts"
	@echo ""

# Create virtual environment
$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

# Install package
install: $(VENV)/bin/activate
	$(BIN)/pip install -e .
	@echo ""
	@echo "Installation complete!"
	@echo ""
	@echo "Quick start:"
	@echo "  source $(VENV)/bin/activate"
	@echo "  captains-log start -f    # Start tracking (foreground)"
	@echo "  captains-log dashboard   # Open web dashboard"
	@echo ""

# Install with dev dependencies
install-dev: $(VENV)/bin/activate
	$(BIN)/pip install -e ".[dev]"
	@echo "Development installation complete!"

# Uninstall
uninstall:
	$(BIN)/pip uninstall -y captains-log
	@echo "Captain's Log uninstalled"

# Run daemon in foreground
run: install
	$(BIN)/captains-log start -f

# Run dashboard
dashboard: install
	$(BIN)/captains-log dashboard

# Run tests
test: install-dev
	$(BIN)/pytest tests/ -v

# Lint code
lint: install-dev
	$(BIN)/ruff check src/

# Format code
format: install-dev
	$(BIN)/ruff format src/

# Type check
typecheck: install-dev
	$(BIN)/mypy src/captains_log

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Deep clean (including venv)
clean-all: clean
	rm -rf $(VENV)

# Build distribution
build: clean install-dev
	$(BIN)/python -m build

# Install launchd service for auto-start
install-service: install
	$(BIN)/captains-log install
	@echo "Service installed. Captain's Log will start on login."

# Uninstall launchd service
uninstall-service: install
	$(BIN)/captains-log uninstall
	@echo "Service uninstalled."

# Show status
status: install
	$(BIN)/captains-log status

# Show health
health: install
	$(BIN)/captains-log health
