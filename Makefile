.PHONY: dev api ui eval test clean setup install check help

# Default target
help:
	@echo "Product Safety Compliance AI"
	@echo ""
	@echo "  make dev       Setup + run CLI evaluation on all products"
	@echo "  make ui        Start web dashboard (localhost:7860)"
	@echo "  make api       Start REST API (localhost:8000)"
	@echo "  make eval      Run CLI evaluation"
	@echo "  make test      Run unit tests"
	@echo "  make setup     Create venv and install deps"
	@echo "  make clean     Clean up"
	@echo ""

# Python and venv settings
PYTHON := python3
VENV := venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTHON_VENV := $(BIN)/python

# Check if .env exists
ENV_FILE := .env
ENV_EXAMPLE := .env.example

# One command: setup + run CLI evaluation
dev: setup check
	@echo "Running evaluation on all products..."
	$(PYTHON_VENV) scripts/run_eval.py

# Start FastAPI server
api: check
	@echo "Starting FastAPI server on http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"
	$(BIN)/uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Start Gradio UI
ui: check
	@echo "Starting Gradio dashboard on http://localhost:7860"
	$(PYTHON_VENV) -m src.ui.app

# Run batch evaluation on all files
eval: check
	@echo "Running batch evaluation..."
	$(PYTHON_VENV) scripts/run_eval.py

# Evaluate specific files/directories
# Usage: make eval-dir DIR=path/to/files
eval-dir: check
	$(PYTHON_VENV) scripts/run_eval.py $(DIR)

# Run tests
test: check
	@echo "Running tests..."
	$(BIN)/pytest tests/ -v

# Setup: create venv and install deps
setup: $(VENV)/touchfile

$(VENV)/touchfile: requirements.txt
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $(VENV)/touchfile
	@echo ""
	@echo "Setup complete!"

# Install deps only (assumes venv exists)
install:
	$(PIP) install -r requirements.txt

# Check environment is ready
check:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Error: Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "Warning: .env file not found. Creating from example..."; \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "Please edit .env and add your OPENAI_API_KEY"; \
		exit 1; \
	fi
	@if ! grep -q "sk-" $(ENV_FILE) 2>/dev/null; then \
		echo "Warning: OPENAI_API_KEY not set in .env"; \
		echo "Please add your API key to .env file"; \
	fi

# Clean up
clean:
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf __pycache__ .pytest_cache
	rm -rf src/__pycache__ src/**/__pycache__
	rm -rf tests/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete!"
