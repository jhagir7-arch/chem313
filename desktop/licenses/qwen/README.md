# Qwen worker retained-license inputs

`scripts/collect_qwen_licenses.py` copies these retained notices plus the
exact CPython and OpenSSL license files passed on its command line into a
release-local `licenses/qwen` directory.  The generated manifest records only
relative artifact paths, package identities, versions and checksums; it never
exports build-machine paths.

The SQLite and mpdecimal files cover the two Homebrew shared libraries named
by the Qwen worker's PyInstaller `COLLECT-00.toc`.  They are retained here so
the collector can produce a self-contained release notice set even when the
Homebrew cellar is unavailable during final packaging.

This directory contains no model weights, adapters, dataset material, or
training records.
