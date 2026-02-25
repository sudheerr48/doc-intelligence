# Publishing to PyPI

## Prerequisites

1. Create accounts:
   - **PyPI**: https://pypi.org/account/register/
   - **TestPyPI** (optional): https://test.pypi.org/account/register/

2. Create API tokens:
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

3. Install build tools:
   ```bash
   pip install build twine
   ```

## Publishing Steps

### 1. Bump version

Edit `pyproject.toml` and update the version:
```toml
version = "5.1.1"
```

### 2. Build

```bash
make build
# or: python -m build
```

This creates `dist/doc_intelligence-{version}-py3-none-any.whl` and `dist/doc_intelligence-{version}.tar.gz`.

### 3. Test on TestPyPI (recommended first time)

```bash
make publish-test
# or: python -m twine upload --repository testpypi dist/*
```

Enter your TestPyPI API token when prompted (`__token__` as username, the token as password).

Verify it works:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ doc-intelligence
```

### 4. Publish to PyPI

```bash
make publish
# or: python -m twine upload dist/*
```

Enter your PyPI API token when prompted.

### 5. Verify

```bash
pip install doc-intelligence
doc-intelligence --help
```

## Sharing with Friends

Once published, friends can install with:

```bash
# Basic install
pip install doc-intelligence

# With all optional features
pip install doc-intelligence[all]

# With specific extras
pip install doc-intelligence[dashboard,ai]
```

## Automating with .pypirc

To avoid entering credentials every time, create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TESTPYPI-TOKEN-HERE
```

Then `make publish` will use saved credentials automatically.

## Version Checklist

Before each release:
- [ ] Update version in `pyproject.toml`
- [ ] Run tests: `make test`
- [ ] Build: `make build`
- [ ] Test install from wheel: `pip install dist/*.whl`
- [ ] Publish: `make publish`
- [ ] Tag release: `git tag v5.1.0 && git push --tags`
