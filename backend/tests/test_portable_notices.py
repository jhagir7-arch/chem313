"""Portable collection must audit Windows payloads and retain exact TOC evidence."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

SPEC = importlib.util.spec_from_file_location(
    "portable_notices", Path(__file__).resolve().parents[2] / "scripts/collect_standalone_licenses.py")
notices = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notices)

BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_portable", Path(__file__).resolve().parents[2] / "scripts/build_portable.py")
portable_build = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(portable_build)

LAUNCHER_SPEC = importlib.util.spec_from_file_location(
    "portable_launcher", Path(__file__).resolve().parents[2] / "desktop/portable.py")
portable_launcher = importlib.util.module_from_spec(LAUNCHER_SPEC)
LAUNCHER_SPEC.loader.exec_module(portable_launcher)


def test_portable_toc_mapping_keeps_owner_for_transformed_payload():
    owner = {"owner": "rdkit", "source_sha256": "verified-source"}
    assert notices.toc_owner("_internal/rdkit/library.dll", {"rdkit/library.dll": owner}) is owner
    assert notices.toc_owner("Contents/Resources/engine/_internal/rdkit/library.so", {"rdkit/library.so": owner}) is owner
    assert notices.toc_owner("_internal/unknown.dll", {}) is None


def test_windows_native_payload_cannot_evade_license_gate(tmp_path):
    for name in ("unknown.dll", "extension.pyd"):
        payload = tmp_path / name
        payload.write_bytes(b"test unowned payload")
        assert notices.is_native(payload)
    rows = notices.native(tmp_path, {"by_sha": {}, "by_path": {}}, {"notices": []}, {})
    assert {r["path"] for r in rows if r["owner"] == "UNMAPPED"} == {"unknown.dll", "extension.pyd"}
    gate = notices.gate({"notices": [1, 2]}, {"required": False}, rows, [], [])
    assert not gate["passed"]
    assert any("unknown.dll" in error for error in gate["failures"])


def test_distribution_review_separates_gcc_runtime_exception_from_lgpl_quadmath(tmp_path):
    for name in ("libgcc_s.so.1", "libstdc++.so.6", "libgfortran-x.so.5", "libquadmath-x.so.0"):
        (tmp_path / name).write_bytes(b"payload")
    review = portable_build.distribution_review(tmp_path)
    assert review["schema"] == "openchem.distribution-review.v2"
    assert review["pending_gcc_runtime_exception_verification"] == [
        "libgcc_s.so.1", "libgfortran-x.so.5", "libstdc++.so.6"
    ]
    assert review["pending_lgpl_corresponding_source"] == ["libquadmath-x.so.0"]
    assert not review["passed"]


def test_distribution_review_requires_hash_bound_gcc_and_quadmath_evidence(tmp_path):
    gcc = tmp_path / "_internal/libgfortran-test.so.5"
    quadmath = tmp_path / "_internal/libquadmath-test.so.0"
    gcc.parent.mkdir(parents=True)
    gcc.write_bytes(b"gcc runtime")
    quadmath.write_bytes(b"quadmath runtime")
    evidence_dir = tmp_path / "licenses/portable-core/linux-gcc-runtime"
    evidence_dir.mkdir(parents=True)
    archive = evidence_dir / "gcc-10.2.1.tar.xz"
    archive.write_bytes(b"official GCC source fixture")
    evidence = {
        "payloads": {
            "_internal/libgfortran-test.so.5": {
                "sha256": portable_build.sha256(gcc),
                "compiler": "GCC 10.2.1",
                "eligible_compilation_evidence": "https://example.test/scipy-wheel-build",
            },
            "_internal/libquadmath-test.so.0": {
                "sha256": portable_build.sha256(quadmath),
                "source_archive": "gcc-10.2.1",
            },
        },
        "source_archives": {
            "gcc-10.2.1": {
                "path": "licenses/portable-core/linux-gcc-runtime/gcc-10.2.1.tar.xz",
                "sha256": portable_build.sha256(archive),
                "url": "https://ftp.gnu.org/gnu/gcc/gcc-10.2.1/gcc-10.2.1.tar.xz",
            }
        },
    }
    (evidence_dir / "GCC-RUNTIME-PROVENANCE.json").write_text(json.dumps(evidence), encoding="utf-8")
    review = portable_build.distribution_review(tmp_path)
    assert review["passed"]
    assert review["cleared_gcc_runtime_exception"] == ["_internal/libgfortran-test.so.5"]
    assert review["cleared_lgpl_corresponding_source"] == ["_internal/libquadmath-test.so.0"]


def test_windows_runtime_terms_acceptance_is_hash_bound(tmp_path):
    terms = tmp_path / portable_launcher.WINDOWS_RUNTIME_TERMS
    terms.write_text("CPython terms", encoding="utf-8")
    args = type("Args", (), {"data": str(tmp_path / "data")})()
    opened = []
    assert portable_launcher.accept_windows_runtime_terms(
        args, terms, open_terms=opened.append, confirm=lambda: True
    )
    assert opened == [str(terms)]
    assert portable_launcher.windows_runtime_terms_accepted(args, terms)
    terms.write_text("changed CPython terms", encoding="utf-8")
    assert not portable_launcher.windows_runtime_terms_accepted(args, terms)
    assert not portable_launcher.accept_windows_runtime_terms(
        args, terms, open_terms=opened.append, confirm=lambda: False
    )


def test_toc_maps_only_hashed_cpython_standard_extensions(tmp_path):
    runtime = tmp_path / "runtime"
    extension = runtime / "lib/python3.13/lib-dynload/_sqlite3.so"
    extension.parent.mkdir(parents=True)
    extension.write_bytes(b"cpython extension")
    license_file = runtime / "LICENSE.txt"
    license_file.write_text("PSF license\n", encoding="utf-8")
    bundle = tmp_path / "bundle/_internal/python3.13/lib-dynload"
    bundle.mkdir(parents=True)
    packaged = bundle / extension.name
    packaged.write_bytes(extension.read_bytes())
    toc_file = tmp_path / "COLLECT-00.toc"
    toc_file.write_text(repr([(packaged.relative_to(tmp_path / "bundle").as_posix(), str(extension), "EXTENSION")]), encoding="utf-8")
    output = tmp_path / "notices"
    output.mkdir()
    py_runtime = notices.runtime(runtime, output, required=True)
    toc = notices.pyinstaller_toc(toc_file, tmp_path / "site", {"by_sha": {}, "by_path": {}}, runtime, py_runtime, output)
    rows = notices.native(tmp_path / "bundle", {"by_sha": {}, "by_path": {}}, py_runtime, toc)
    assert rows[0]["owner"] == "CPython"
    assert rows[0]["source_sha256"] == notices.sha256(extension)
    assert rows[0]["mapping_method"] == notices.CPYTHON_EXTENSION_MAPPING
    packaged.write_bytes(b"changed packaged extension")
    assert notices.native(tmp_path / "bundle", {"by_sha": {}, "by_path": {}}, py_runtime, toc)[0]["owner"] == "UNMAPPED"


def test_toc_maps_cpython_windows_dlls_but_not_runtime_third_party_dlls(tmp_path):
    runtime = tmp_path / "runtime"
    cpython = runtime / "DLLs/_sqlite3.pyd"
    third_party = runtime / "DLLs/libssl-3.dll"
    cpython.parent.mkdir(parents=True)
    cpython.write_bytes(b"cpython")
    third_party.write_bytes(b"openssl")
    (runtime / "LICENSE.txt").write_text("PSF license\n", encoding="utf-8")
    bundle = tmp_path / "bundle/_internal"
    bundle.mkdir(parents=True)
    (bundle / cpython.name).write_bytes(cpython.read_bytes())
    (bundle / third_party.name).write_bytes(third_party.read_bytes())
    toc_file = tmp_path / "COLLECT-00.toc"
    toc_file.write_text(repr([(f"_internal/{cpython.name}", str(cpython), "EXTENSION"), (f"_internal/{third_party.name}", str(third_party), "BINARY")]), encoding="utf-8")
    output = tmp_path / "notices"
    output.mkdir()
    py_runtime = notices.runtime(runtime, output, required=True)
    toc = notices.pyinstaller_toc(toc_file, tmp_path / "site", {"by_sha": {}, "by_path": {}}, runtime, py_runtime, output)
    rows = {row["path"]: row for row in notices.native(tmp_path / "bundle", {"by_sha": {}, "by_path": {}}, py_runtime, toc)}
    assert rows["_internal/_sqlite3.pyd"]["owner"] == "CPython"
    assert rows["_internal/libssl-3.dll"]["owner"] == "UNMAPPED"


def test_toc_maps_documented_windows_cpython_third_party_runtime_dlls(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "LICENSE.txt").write_text("PSF license\n", encoding="utf-8")
    source_files = {
        "libcrypto-3.dll": b"openssl crypto",
        "libssl-3.dll": b"openssl ssl",
        "libffi-8.dll": b"libffi",
        "sqlite3.dll": b"sqlite",
        "api-ms-win-core-fibers-l1-1-0.dll": b"Microsoft API-set",
        "ucrtbase.dll": b"Microsoft UCRT",
        "VCRUNTIME140.dll": b"Microsoft VCRUNTIME",
    }
    bundle = tmp_path / "bundle/_internal"
    bundle.mkdir(parents=True)
    toc_rows = []
    for name, contents in source_files.items():
        source = runtime / name
        source.write_bytes(contents)
        (bundle / name).write_bytes(contents)
        toc_rows.append((f"_internal/{name}", str(source), "BINARY"))
    toc_file = tmp_path / "COLLECT-00.toc"
    toc_file.write_text(repr(toc_rows), encoding="utf-8")
    project = tmp_path / "project"
    retained = project / "desktop/licenses/portable-runtime"
    retained.mkdir(parents=True)
    for filename in {item[1] for item in notices.WINDOWS_CPYTHON_RUNTIME_NOTICES.values()}:
        (retained / filename).write_text(filename, encoding="utf-8")
    (retained / notices.WINDOWS_CPYTHON_CRT_NOTICE).write_text("CPython CRT conditions", encoding="utf-8")
    output = tmp_path / "notices"
    output.mkdir()
    monkeypatch.setattr(notices.sys, "platform", "win32")
    py_runtime = notices.runtime(runtime, output, required=True)
    toc = notices.pyinstaller_toc(toc_file, tmp_path / "site", {"by_sha": {}, "by_path": {}}, runtime, py_runtime, output, project)
    rows = {row["path"]: row for row in notices.native(tmp_path / "bundle", {"by_sha": {}, "by_path": {}}, py_runtime, toc)}
    assert rows["_internal/libcrypto-3.dll"]["owner"] == "OpenSSL-3"
    assert rows["_internal/libssl-3.dll"]["owner"] == "OpenSSL-3"
    assert rows["_internal/libffi-8.dll"]["owner"] == "libffi"
    assert rows["_internal/sqlite3.dll"]["owner"] == "SQLite"
    assert rows["_internal/libffi-8.dll"]["mapping_method"] == notices.WINDOWS_CPYTHON_RUNTIME_MAPPING
    assert rows["_internal/ucrtbase.dll"]["owner"] == "Microsoft Distributable Code via CPython 3.13.16"
    assert rows["_internal/VCRUNTIME140.dll"]["owner"] == "Microsoft Distributable Code via CPython 3.13.16"
    for name in ("api-ms-win-core-fibers-l1-1-0.dll", "ucrtbase.dll", "VCRUNTIME140.dll"):
        row = rows[f"_internal/{name}"]
        assert row["official_terms"] == list(notices.WINDOWS_MICROSOFT_RUNTIME_TERMS)
        assert row["notices"][0]["path"].endswith(notices.WINDOWS_CPYTHON_CRT_NOTICE)


def test_linux_system_library_requires_package_copyright(tmp_path, monkeypatch):
    # Keep the simulated Debian path POSIX-shaped even while pytest runs on Windows.
    source = PurePosixPath("/usr/lib/libportable-notice-test.so")
    doc_root = tmp_path / "doc"
    copyright_file = doc_root / "libportable-test/copyright"
    copyright_file.parent.mkdir(parents=True)
    copyright_file.write_text("The license is /usr/share/common-licenses/GPL-2.\n", encoding="utf-8")
    common_root = tmp_path / "common"
    common_root.mkdir()
    (common_root / "GPL-2").write_text("GPL text\n", encoding="utf-8")

    class Result:
        def __init__(self, stdout):
            self.stdout = stdout

    def run(args, **_kwargs):
        if args[1] == "--search":
            return Result("libportable-test:amd64: /usr/lib/libportable-notice-test.so\n")
        return Result("1.2.3\n")

    monkeypatch.setattr(notices.subprocess, "run", run)
    monkeypatch.setattr(notices.sys, "platform", "linux")
    monkeypatch.setattr(notices, "sha256", lambda path: "source-hash" if path == source else __import__("hashlib").sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(notices, "debian_system_aliases", lambda value: [source])
    owner = notices.debian_system_owner(source, tmp_path / "out", doc_root, common_root)
    assert owner["package"] == "libportable-test:amd64"
    assert owner["package_version"] == "1.2.3"
    assert owner["notices"][0]["path"] == "system/libportable-test/copyright"
    assert owner["notices"][1]["path"] == "system/libportable-test/common-licenses/GPL-2"
    (common_root / "GPL-2").unlink()
    assert notices.debian_system_owner(source, tmp_path / "out-missing", doc_root, common_root) is None


def test_linux_system_library_uses_only_hash_verified_usrmerge_alias_and_reports_missing_notice(tmp_path, monkeypatch):
    # These are simulated Linux filesystem paths, not host-native test paths.
    source = PurePosixPath("/lib/libportable-alias.so")
    alias = PurePosixPath("/usr/lib/libportable-alias.so")
    doc_root = tmp_path / "doc"
    (doc_root / "libportable-alias").mkdir(parents=True)
    # Deliberately omit GPL-2 so the diagnostic proves the strict notice gate.
    (doc_root / "libportable-alias/copyright").write_text("/usr/share/common-licenses/GPL-2.\n", encoding="utf-8")
    queries = []

    class Result:
        def __init__(self, stdout):
            self.stdout = stdout

    def run(args, **_kwargs):
        if args[1] == "--search":
            queries.append(args[-1])
            if args[-1] == str(source):
                raise subprocess.CalledProcessError(1, args)
            assert args[-1] == str(alias)
            return Result(f"libportable-alias:amd64: {alias}\n")
        return Result("1.2.3\n")

    monkeypatch.setattr(notices.subprocess, "run", run)
    monkeypatch.setattr(notices.sys, "platform", "linux")
    # Exercise exactly the real usrmerge shape while keeping all paths temporary.
    monkeypatch.setattr(notices, "debian_system_aliases", lambda value: [source, alias])
    owner, diagnostic = notices.debian_system_owner_detail(source, tmp_path / "out", doc_root, tmp_path / "common")
    assert owner is None
    assert queries == [str(source), str(alias)]
    assert diagnostic == {
        "code": "DEBIAN_COMMON_LICENSE_MISSING",
        "source_path": str(source),
        "package": "libportable-alias:amd64",
        "common_license": "GPL-2",
    }


def test_native_keeps_safe_debian_unmapped_diagnostic(tmp_path):
    diagnostic = {"code": "DPKG_OWNERSHIP_LOOKUP_FAILED", "source_path": "/usr/lib/libexample.so"}
    payload = tmp_path / "missing.so"
    payload.write_bytes(b"unmapped native")
    rows = notices.native(tmp_path, {"by_sha": {}, "by_path": {}}, {"notices": []}, {"missing.so": {"owner": "UNMAPPED", "diagnostic": diagnostic}})
    assert rows == [{"path": "missing.so", "owner": "UNMAPPED", "source": "UNMAPPED", "packaged_sha256": notices.sha256(payload), "notices": [], "diagnostic": diagnostic}]


def test_ui_provenance_exempts_unemitted_build_dependency_but_not_emitted_dev_package(tmp_path):
    modules = tmp_path / "node_modules"
    for name, payload in (("build-only", b"native build binary"), ("emitted-dev", b"ui module source")):
        package = modules / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": name, "version": "1.0.0", "license": "MIT"}), encoding="utf-8")
        (package / "payload.bin").write_bytes(payload)
    lockfile = tmp_path / "package-lock.json"
    lockfile.write_text(json.dumps({"packages": {"node_modules/build-only": {"version": "1.0.0"}, "node_modules/emitted-dev": {"version": "1.0.0", "dev": True}}}), encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    emitted = dist / "app.js"
    emitted.write_bytes(b"compiled UI")
    provenance = dist / "ui-provenance.json"
    provenance.write_text(json.dumps({"schema": "openchem.ui-provenance.v1", "packages": ["node_modules/emitted-dev"], "files": [{"path": "app.js", "sha256": notices.sha256(emitted)}]}), encoding="utf-8")
    ui = notices.ui_provenance(provenance)
    rows = notices.collect_npm(lockfile, modules, tmp_path / "out", tmp_path, ui)
    by_name = {row["name"]: row for row in rows}
    assert by_name["build-only"]["state"] == "NOT_EMITTED_BUILD_DEPENDENCY"
    assert by_name["emitted-dev"]["review"] == "MISSING_NOTICE_FOR_EMITTED_UI_PACKAGE"
    assert notices.gate({"notices": [1, 2]}, {"required": False}, [], [], [by_name["build-only"]], ui)["passed"]
    assert not notices.gate({"notices": [1, 2]}, {"required": False}, [], [], rows, ui)["passed"]


def test_ui_provenance_rejects_stale_or_missing_file_inventory(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "app.js").write_bytes(b"compiled UI")
    provenance = dist / "ui-provenance.json"
    provenance.write_text(json.dumps({"schema": "openchem.ui-provenance.v1", "packages": [], "files": []}), encoding="utf-8")
    try:
        notices.ui_provenance(provenance)
    except SystemExit as exc:
        assert "files or hashes" in str(exc)
    else:
        raise AssertionError("stale UI provenance must fail closed")
