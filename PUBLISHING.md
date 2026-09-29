# Publishing to PyPI (maintainers)

This project publishes **beta releases** through GitHub Actions and PyPI Trusted Publishing
(OIDC). **No long-lived PyPI API token is required.**

## One-time setup (repository owner)

1. At GitHub, create an environment named **pypi** in
   Settings -> Environments -> New environment. For stronger release security, enable
   deployment protection (required reviewers, if supported on your plan) and
   restrict deployment tags to `v*` as appropriate.
2. Sign in to https://pypi.org/ and open
   Account settings -> Publishing -> Add a new pending publisher.
   Set the **exact** values:

   | Field | Value |
   |---|---|
   | PyPI project name | `scratch-link-bleak` |
   | GitHub owner | `rril` |
   | GitHub repository | `scratch-link-bleak` |
   | Workflow filename | `release.yml` |
   | Environment name | `pypi` |

   Submit the pending publisher *before* publishing your first GitHub Release.
   Pending publisher setup does not reserve the name: PyPI creates the project
   only when the first valid GitHub Actions publish completes.

## Publishing v0.2.0b1

Check `pyproject.toml` has `version = "0.2.0b1"` and that GitHub tests pass.
At https://github.com/rril/scratch-link-bleak/releases/new :

- Tag: `v0.2.0b1` (create the tag from **main**)
- Title: `Scratch Link Bleak v0.2.0 Beta 1`
- Check **Set as a pre-release**.
- Review the release notes, then select **Publish release**.

The `.github/workflows/release.yml` workflow starts on `release.published`:
1. Checks out the release tag.
2. Verifies the package's version matches the tag.
3. Runs smoke tests, builds sdist and wheel, and checks package metadata.
4. Uploads artifacts and publishes through short-lived GitHub OIDC credentials
   using `pypa/gh-action-pypi-publish`, with environment `pypi`.

Check the Actions tab and then check
https://pypi.org/project/scratch-link-bleak/.

### Test after upload

In a new virtual environment, run:

```bash
python3 -m venv /tmp/scratch-link-pypi-check
source /tmp/scratch-link-pypi-check/bin/activate
python -m pip install --index-url https://pypi.org/simple/ 'scratch-link-bleak==0.2.0b1'
scratch-link-bleak --help
python -m pip show pyscrlink bluepy
```

The last command should report missing packages: neither is a dependency.

**PyPI files/versions are immutable.** If a published build is defective,
fix the code and publish a *new* version; do not attempt to replace the old file.

Do not upload `server.key`, certificates generated for an individual machine,
or PyPI credentials. The source distribution intentionally generates user-local
TLS material only when `scratch-link-bleak --setup` is invoked.
