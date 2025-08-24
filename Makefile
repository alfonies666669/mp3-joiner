# ---------- Settings ----------
SHELL := /bin/bash
.ONESHELL:
.SILENT:

PYTHON ?= python3.13
VENV := .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PY := $(BIN)/python

SRC := app.py tools logger
TESTS := tests

ifneq (,$(wildcard .env))
	include .env
	export $(shell sed -n 's/^\([^#][A-Za-z_0-9]*\)=.*/\1/p' .env)
endif

# ---------- Phony ----------
.PHONY: help init install install-dev pre-commit format format-file lint mypy test run gunicorn clean deepclean

# ---------- Help ----------
help:
	echo "make init          # создать .venv (Python 3.13)"
	echo "make install       # установить runtime-зависимости"
	echo "make install-dev   # установить runtime+dev-зависимости"
	echo "make pre-commit    # установить git-хуки pre-commit"
	echo "make format        # isort(по длине)+black по коду"
	echo "make format-file FILE=path.py"
	echo "make lint          # ruff (без автоправок)"
	echo "make mypy          # mypy (если включил)"
	echo "make test          # pytest"
	echo "make run           # запустить app.py с .env"
	echo "make gunicorn      # запустить gunicorn на 0.0.0.0:5001"
	echo "make clean         # убрать кэш"
	echo "make deepclean     # убрать venv и кэш"

# ---------- Env ----------

init:
	echo ">>> Removing old venv if exists"
	rm -rf $(VENV)
	echo ">>> Creating new venv with $(PYTHON)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

install: $(VENV)
	$(PIP) install -r requirements.txt

install-dev: $(VENV)
	# requirements-dev.txt должен включать '-r requirements.txt'
	$(PIP) install -r requirements-dev.txt

pre-commit: $(VENV)
	$(PIP) install pre-commit
	$(BIN)/pre-commit install
	echo ">>> pre-commit hooks installed"

# ---------- Code quality ----------
format: $(VENV)
	# Импорты по длине (isort) + форматирование (black)
	$(BIN)/isort --settings-path=pyproject.toml $(SRC) $(TESTS) || true
	$(BIN)/black --config=pyproject.toml $(SRC) $(TESTS) || true

format-file: $(VENV)
	@if [ -z "$(FILE)" ]; then echo "Usage: make format-file FILE=path/to/file.py"; exit 1; fi
	$(BIN)/isort --settings-path=pyproject.toml $(FILE) || true
	$(BIN)/black --config=pyproject.toml $(FILE) || true

lint: $(VENV)
	# Статический анализ (без автоправок)
	$(BIN)/ruff check .

mypy: $(VENV)
	# Запустится, только если mypy установлен
	if $(BIN)/python -c "import mypy" >/dev/null 2>&1; then \
		$(BIN)/mypy . ; \
	else \
		echo "mypy not installed. Run 'make install-dev' to add it."; \
	fi

lint-pylint:
    @.venv/bin/pylint app.py tools logger --rcfile=.pylintrc || true

test: $(VENV)
	$(BIN)/pytest -q

# ---------- Run ----------
run: $(VENV)
	# Использует переменные из .env, если есть
	[ -n "$$SECRET_KEY" ] || export SECRET_KEY="dev-insecure-change-me"
	[ -n "$$ALLOWED_ORIGIN" ] || export ALLOWED_ORIGIN="http://localhost:5001"
	$(PY) app.py

gunicorn: $(VENV)
	# Продовый запуск локально
	[ -n "$$SECRET_KEY" ] || export SECRET_KEY="dev-insecure-change-me"
	[ -n "$$ALLOWED_ORIGIN" ] || export ALLOWED_ORIGIN="http://localhost:5001"
	$(BIN)/gunicorn --workers 1 --timeout 300 --bind 0.0.0.0:5001 app:app

# ---------- Clean ----------
clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	find . -name "*.pyc" -delete || true
	rm -rf .ruff_cache .mypy_cache .pytest_cache || true

deepclean: clean
	rm -rf $(VENV)
