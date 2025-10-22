# Light Sequence Controller Tests

This directory contains the test suite for the Light Sequence Controller.

## Test Structure

- `test_imports.py` - Tests that all modules can be imported correctly
- `controller/` - Tests for controller functionality
  - `test_sequence.py` - Sequence management tests
  - `test_preset_manager.py` - Preset management tests
  - `test_config.py` - Configuration tests
  - `test_utils.py` - Utility function tests
- `simulation/` - Tests for simulation mode
  - `test_light_software_sim.py` - Light software simulator tests
- `gui/` - GUI tests (to be implemented)

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test file
```bash
uv run pytest tests/test_imports.py
```

### Run tests with coverage
```bash
uv run pytest --cov=src --cov-report=html
```

### Run only fast tests (skip slow ones)
```bash
uv run pytest -m "not slow"
```

### Run only unit tests
```bash
uv run pytest -m unit
```

### Run with verbose output
```bash
uv run pytest -v
```

### Run specific test by name
```bash
uv run pytest tests/controller/test_sequence.py::test_add_sequence
```

## Test Markers

- `@pytest.mark.slow` - Marks slow-running tests
- `@pytest.mark.integration` - Marks integration tests
- `@pytest.mark.unit` - Marks unit tests
- `@pytest.mark.gui` - Marks tests that require GUI

## Writing New Tests

1. Create test files with the prefix `test_`
2. Write test functions with the prefix `test_`
3. Use fixtures from `conftest.py` for common setup
4. Add appropriate markers for test categorization

## Dependencies

The test suite requires:
- pytest
- pytest-cov (for coverage reports)

These are included in the project's dev dependencies.
