# CN test categories

## Portable unit tests (default CI)

Windows, Python 3.11:

```powershell
python -m pip install -r requirements.txt -c tools/ci-constraints.txt
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tools -p "test_*.py"
```

Tests use generated arrays, upstream generic templates and mocked device inputs. Default discovery explicitly skips local integration checks rather than counting them as passed. No BlueStacks, game, user template, private screenshot or external launcher is required. UI-generation comparison locates `pyside6-uic` in the current Python installation’s Scripts directory; CI pins the tested Qt version.

## Local integration tests (explicit opt-in)

`FGO_RUN_LOCAL_INTEGRATION=1` enables the two deployment-specific launcher checks and one saved-screenshot regression. A missing local launcher or screenshot causes failure; it is not silently accepted. The saved-image detector does not send device input.

```powershell
$env:FGO_RUN_LOCAL_INTEGRATION = '1'
$env:FGO_PRIVATE_FIXTURE_DIR = '<private local screenshot directory>'
python -m unittest discover -s tools -p "test_*.py"
```

The standalone `tools/test_cn_battle_continue.py` CLI and `tools/check_free_return.py` remain available for explicit local screenshot inputs. Never commit the private fixture directory or publish its images/logs as artifacts. Live navigation and battle tests are separate manual integration work and are not performed by this CI.

## CI boundaries

`cn-tests.yml` runs on pushes to `cn-dev`, pull requests and manual dispatch, with read-only repository permission. It does not upload artifacts, build a release, operate a device, or publish an EXE. Existing upstream mirror/build workflows remain in the tree for attribution/synchronization but are guarded to run only in the official upstream repository.

Dependency constraints reflect the existing tested environment. CI dependency resolution and execution must still be verified on the actual GitHub-hosted runner; local results are not a substitute for a GitHub Actions result.
