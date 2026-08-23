# Contributing to Friday V2

Thank you for your interest in contributing to Friday V2! This document explains our development process and expectations.

## Development Process

Friday follows a **Proof-Based Development** discipline where every feature must ship with raw evidence of its correctness.

### The Gate System

Each major piece of functionality goes through a progressive gate:

| Gate | What it Proves |
|------|-----------------|
| Gate 1 | L1 primitives work on the target platform |
| Gate 2 | L0 observability logs correctly |
| Gate 3 | L2 verification checks are pure read-only |
| Gate 4 | L3 executor runs plans correctly |
| Gate 5 | L4 planner produces valid plans |
| Gate 6 | Composite tasks complete end-to-end |

### Capability Gap Loop

When you need a new primitive, follow this process:

1. **Expose the gap**: Write a failed goal or let the watch loop discover it
2. **Triage**: Run `./.venv/bin/python -m friday.gap_triage`
3. **Review draft**: Check `gates/proposed_primitives/<primitive>/`
4. **Automated gate**: Run `. .venv/bin/python -m friday.register_proposal --proposal ...`
5. **Human approval**: Edit `APPROVED.md` and sign off
6. **Register**: The gate registers the primitive and re-runs the original goal

## Setting Up Your Environment

```bash
# Clone
git clone https://github.com/lakshay/Friday-V2.git
cd Friday-V2

# Virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows

# Install
pip install -e ".[dev,test]"

# Install Playwright browsers
playwright install chromium

# Install git hooks (optional but recommended)
pre-commit install
```

## Running Tests

```bash
# Run all tests
python -m pytest -v

# Run with coverage
python -m pytest --cov=friday --cov-report=xml

# Run specific test
python -m pytest tests/test_window.py -v

# Run gates (which generate proof files)
python gates/test_suite.py
```

## Code Style

We use **ruff** for linting and formatting:

```bash
# Format code
ruff format .

# Lint
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Type checking
mypy friday

# All quality checks
ruff check . && ruff format . && mypy friday
```

### Style Guide

- **Line length**: 100 characters
- **Quotes**: Double quotes for strings
- **Imports**: Sorted with isort, grouped by source
- **Type hints**: Required for all public functions
- **Docstrings**: Following Google style

### Example

```python
@contract(
    precondition="Window is already focused.",
    postcondition="Window loses focus within 1s.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
)
def unfocus_window() -> bool:
    """Send Alt+Tab to the current window.

    Returns True if focus changed, False if already unfocused.
    """
    # Implementation
```

## Adding a New Primitive

### 1. Create the Module

Create `friday/l1/<module>.py` with your primitive:

```python
from friday.contracts import contract, Idempotency

@contract(
    precondition="Input file exists.",
    postcondition="Output file is created.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if file operations fail",
    returns="str: path to created file",
)
def new_primitive(input_path: str, output_path: str) -> str:
    """Your primitive's docstring."""
    # Implementation
```

### 2. Write Tests

Create `tests/test_<module>.py` with comprehensive tests:

- Normal operation cases
- Precondition failures
- API/auth errors
- Platform-specific branches (Linux vs Windows)
- Edge cases

### 3. Update the Catalog

The `_discover_l1_modules()` function in `friday/l4/planner.py` auto-discovers new modules. If you're close to the 2026-08-13 bug, ensure your module is in `_L1_MODULES` as a fallback.

### 4. Register Through the Loop

Use `python -m friday.gap_triage` to draft the proposal, then follow the capability gap loop.

## Platform Support

Friday supports:
- **Linux**: Hyprland Wayland compositor
- **Windows**: Windows 11 24H2+ (build 26100 or later)

### Platform-Specific Code

```python
def _is_windows() -> bool:
    return os.name == "nt"

def my_function():
    if _is_windows():
        return _win_implementation()
    return _posix_implementation()
```

## Documentation

- **User Guide**: `docs/user-guide.md` - Getting started
- **MCP Server**: `docs/mcp.md` - wiring Friday's primitives into Claude Desktop / Claude Code / Cursor
- **Architecture**: `docs/architecture.md` - System design
- **API Reference**: Generated from docstrings
- **README.md**: Main entry point

Update documentation when adding features. For new primitives, the docstring becomes part of the live catalog.

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Update documentation
6. Ensure all tests pass: `python -m pytest`
7. Ensure linting passes: `ruff check . && ruff format .`
8. Ensure type checking passes: `mypy friday`
9. Push to your fork
10. Open a pull request

### PR Requirements

- **Proof of work**: For significant features, include evidence of it working
- **Tests**: At least 90% coverage for new code
- **Documentation**: Update docs as needed
- **Commit messages**: Follow conventional commits format

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.