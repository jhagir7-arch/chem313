# Standalone Apple Silicon distribution

The standalone app embeds its CPython interpreter, frozen service, numerical
worker code, scientific release wheels and prebuilt browser assets. End users
install the app by dragging it to Applications. Node, npm, uv and Python are
maintainer build dependencies only.

On an Apple Silicon Mac with Xcode command-line tools, first set up the locked
source runtime using `scripts/setup_public_runtime.sh`, then run:

```sh
.venv/bin/python -m pip install -r desktop/requirements-lock.txt
bash scripts/build_standalone_app.sh dist/chem313/Chem313.app
.venv/bin/python scripts/test_standalone_package.py dist/chem313/Chem313.app build/standalone/api-check.json
.venv/bin/python scripts/audit_standalone_binary.py dist/chem313/Chem313.app build/standalone/binary-audit.json
bash scripts/package_standalone_mac.sh
```

The builder refuses to overwrite the app. Use another output path for a new
build. It does not copy development engine catalogs, private acquisition
receipts, research data, model weights or the old multi-worker distribution.
`bundle.json` records exactly which scientific worker operations are included;
the runtime filters operation discovery and rejects unavailable jobs before
creating a durable record. Source-mode optional workers retain their existing
behavior. The two bundled recipe operations run in separate instances of the
embedded executable, with the same bounds as existing trusted workers.

The notice gate captures Python wheel license trees, CPython's runtime license,
production JavaScript notices, project licensing, fonts and native libraries.
PyInstaller changes native load paths and signatures, so the manifest records
both the original wheel RECORD checksum and the packaged checksum, joined via
that build's collection TOC. It does not claim an upstream source commit for a
release wheel or general scientific validation.

## Apple distribution signing

The local preview is ad-hoc signed. It has no Developer ID identity or
notarization ticket. An Internet download can therefore trigger Gatekeeper.
To provide the normal verified download experience, a release maintainer must
use their Apple Developer ID Application identity to sign every embedded
Mach-O file with the hardened runtime and timestamp, collect the notice
manifest again after those signatures change the native hashes, then sign the
outer app. Submit the app ZIP with `xcrun notarytool submit` using a configured
keychain profile, require an Accepted result and staple the ticket to the app.
Package the stapled app, notarize/staple the DMG, and verify both with `codesign`,
`spctl` and `xcrun stapler validate`. Do not publish an ad-hoc preview as a
notarized release. See Apple's [Developer ID distribution guidance](https://developer.apple.com/developer-id/).

## Compatibility and validation limits

Run the binary audit for every candidate: the embedded runtime may require a
newer macOS version than the native launcher. Set the bundle minimum to at least
the highest embedded deployment target before packaging. Testing here uses
macOS 27 arm64; other macOS versions and Intel/Rosetta are unverified. Quantum ORCA execution requires a separately
licensed executable and was not exercised as part of this standalone-core
verification. ORCA preparation/results and numerical reference checks are
separate from validating the scientific suitability of a calculation.
