.PHONY: install check lint clean

install:
	pip install -r requirements.txt

check:
	python -m py_compile scripts/*.py
	python scripts/validate_artifact.py sender-profile templates/sender-profile.example.json
	python scripts/validate_artifact.py smtp-config templates/smtp-config.example.json

lint:
	pip install ruff mypy 2>/dev/null || true
	ruff check scripts/
	mypy scripts/ --ignore-missing-imports 2>/dev/null || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete
	rm -rf .eggs *.egg-info dist build
