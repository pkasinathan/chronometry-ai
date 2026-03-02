# Chronometry Release Checklist

Use this checklist before publishing a new release.

## 1) Preflight

- Confirm working tree is clean or intentionally scoped
- Confirm target version in `pyproject.toml`
- Confirm `CHANGELOG.md` includes that version and date

## 2) Documentation pass

- Update user-facing docs:
  - `README.md`
  - `QUICK_START.md`
  - `FAQ.md`
  - `TROUBLESHOOTING.md`
  - `config/README.md`
- Verify docs match current behavior:
  - `system_config.yaml` defaults + `user_config.yaml` overrides
  - Dashboard Settings includes System Health + Reset to Defaults
  - Default models and fallback values are accurate
  - Commands use `pip3` where appropriate

## 3) Quality gates

Run locally:

```bash
make check
make test
```

Optional coverage check:

```bash
make test-cov
```

## 4) Build artifacts

```bash
python3 -m pip install --upgrade build twine
python3 -m build
python3 -m twine check dist/*
```

## 5) Final validation smoke

```bash
chrono version
chrono init --force
chrono validate
chrono service install
chrono status
```

Manual UI checks:

- Open `http://localhost:8051`
- Settings: save config and confirm backup created
- Settings: Reset to Defaults works
- Settings: System Health values update during activity

## 6) Publish

- Create release commit
- Tag version (`vX.Y.Z`)
- Push branch and tag
- Publish to PyPI (project workflow/manual process)
- Draft GitHub release notes from `CHANGELOG.md`

## 7) Post-release

- Verify `pip3 install -U chronometry-ai` pulls the new version
- Verify `chrono version` reports expected version
- Announce release with highlights and migration notes (if any)
