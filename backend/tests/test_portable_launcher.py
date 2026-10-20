import importlib.util
import io
import json
from pathlib import Path
import sys
import types

from hypothesislab.desktop import platform_data_dir
from hypothesislab import science_jobs, science_worker
from hypothesislab.store import Store


PORTABLE = Path(__file__).resolve().parents[2] / "desktop" / "portable.py"
SPEC = importlib.util.spec_from_file_location("openchem_portable", PORTABLE)
portable = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(portable)

BUILD = Path(__file__).resolve().parents[2] / "scripts" / "build_portable.py"
BUILD_SPEC = importlib.util.spec_from_file_location("build_portable", BUILD)
build_portable = importlib.util.module_from_spec(BUILD_SPEC)
assert BUILD_SPEC.loader is not None
BUILD_SPEC.loader.exec_module(build_portable)


def test_platform_data_dir_uses_native_user_locations():
    assert platform_data_dir(environ={"LOCALAPPDATA": "C:/Profiles/Test/AppData/Local"}, system="win32", home="/home/test") == Path("C:/Profiles/Test/AppData/Local/OpenChem")
    assert platform_data_dir(environ={"XDG_DATA_HOME": "/data"}, system="linux", home="/home/test") == Path("/data/OpenChem")
    assert platform_data_dir(environ={}, system="linux", home="/home/test") == Path("/home/test/.local/share/OpenChem")
    assert platform_data_dir(environ={}, system="darwin", home="/mock-home/test") == Path("/mock-home/test/Library/Application Support/OpenChem")


def test_launcher_opens_only_after_loopback_readiness():
    opened = []
    commands = []

    class Process:
        stdout = io.StringIO('{"url":"http://127.0.0.1:43123","pid":4}\n')

    args = type("Args", (), {"data": None, "ui": None, "port": 0, "no_browser": False})()
    process, url = portable.launch(args, process_factory=lambda command, **kw: (commands.append(command) or Process()), browser_open=lambda url, new: opened.append((url, new)))
    assert process.__class__ is Process
    assert url == "http://127.0.0.1:43123"
    assert opened == [("http://127.0.0.1:43123", 1)]
    assert commands[0][-1] == "--serve"


def test_launcher_rejects_non_loopback_readiness():
    try:
        portable.readiness_url(io.StringIO('{"url":"http://example.test:80"}\n'))
    except RuntimeError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("non-loopback readiness was accepted")


def test_worker_dispatch_is_lazy(monkeypatch):
    calls = []
    fake_worker = types.ModuleType("hypothesislab.science_worker")
    fake_worker.main = lambda: calls.append("worker")
    monkeypatch.setitem(sys.modules, "hypothesislab.science_worker", fake_worker)
    assert portable.main(["--science-worker"]) == 0
    assert calls == ["worker"]


def test_service_dispatch_forwards_only_service_arguments(monkeypatch):
    import hypothesislab.desktop
    calls = []
    monkeypatch.setattr(hypothesislab.desktop, "main", lambda argv: calls.append(argv))
    assert portable.main(["--serve", "--data", "saved-data", "--ui", "built-ui", "--port", "43123"]) == 0
    assert calls == [["--data", "saved-data", "--ui", "built-ui", "--port", "43123"]]


def test_main_retains_service_lifecycle(monkeypatch):
    calls = []

    class Process:
        def wait(self):
            calls.append("wait")
            return 0

        def terminate(self):
            calls.append("terminate")

    monkeypatch.setattr(portable, "launch", lambda args: (Process(), "http://127.0.0.1:1"))
    assert portable.main(["--no-browser"]) == 0
    assert calls == ["wait"]


def test_portable_profile_uses_current_architecture(monkeypatch, tmp_path):
    monkeypatch.setattr(build_portable.metadata, "version", lambda package: "test-version")
    monkeypatch.setattr(build_portable.platform, "machine", lambda: "test-arch")
    profile = tmp_path / "bundle.json"
    build_portable.write_profile(profile)
    data = json.loads(profile.read_text())
    assert data["schema"] == "openchem.standalone.v1"
    assert data["distribution"] == "chem313-portable-core"
    assert data["product_name"] == "Chem313"
    assert data["legacy_data_product_name"] == "OpenChem"
    assert data["architecture"] == "test-arch"
    assert data["platform"] == build_portable.platform_id()


def test_portable_profile_maps_win32_to_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(build_portable.metadata, "version", lambda package: "test-version")
    monkeypatch.setattr(build_portable.sys, "platform", "win32")
    profile = tmp_path / "bundle.json"
    build_portable.write_profile(profile)
    assert json.loads(profile.read_text())["platform"] == "windows"


def test_worker_reports_unavailable_posix_limits_on_windows(monkeypatch):
    monkeypatch.setattr(science_worker, "resource", None)
    assert science_worker.resource_limits() == {"cpu": "UNAVAILABLE_ON_PLATFORM", "file_size": "UNAVAILABLE_ON_PLATFORM"}
    assert science_worker.resource_usage() == (None, None)


def test_worker_normalizes_linux_max_rss_to_bytes(monkeypatch):
    fake_resource = types.SimpleNamespace(RUSAGE_SELF=object(), getrusage=lambda _: types.SimpleNamespace(ru_utime=1.5, ru_maxrss=12))
    monkeypatch.setattr(science_worker, "resource", fake_resource)
    monkeypatch.setattr(science_worker.sys, "platform", "linux")
    assert science_worker.resource_usage() == (1.5, 12 * 1024)


def test_windows_job_stop_uses_process_methods_not_killpg(monkeypatch):
    calls = []

    class Process:
        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout):
            calls.append(("wait", timeout))
            return 0

    monkeypatch.setattr(science_jobs.os, "name", "nt")
    monkeypatch.setattr(science_jobs.os, "killpg", lambda *args: (_ for _ in ()).throw(AssertionError("killpg called")), raising=False)
    science_jobs.ScienceJobs._stop(Process())
    assert calls == ["terminate", ("wait", 2)]
    assert science_jobs.worker_process_options() == {"creationflags": getattr(science_jobs.subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}


def test_store_preserves_raw_bytes_and_audit_records_on_native_host(tmp_path):
    store = Store(tmp_path)
    raw = "α,1\r\nβ,2\n".encode("utf-8") + b"\x1a\n"
    artifact = store.put("portable", "originals", "txt", raw)
    assert store.put("portable", "originals", "txt", raw) == artifact
    event = store.event("portable", "fixture.saved", "fixture", [artifact], {"label": "α"})
    expected = (json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    assert (tmp_path / "portable/events.jsonl").read_bytes() == expected
    assert store.events("portable") == [event]
    assert store.verify_artifacts("portable")["status"] == "PASS"


def test_gcc_runtime_binary_requires_source_review_before_distribution(tmp_path):
    library = tmp_path / "_internal/scipy.libs/libgfortran-123.so.5"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"native fixture")
    review = build_portable.distribution_review(tmp_path)
    assert review["passed"] is False
    assert review["pending_corresponding_source"] == ["_internal/scipy.libs/libgfortran-123.so.5"]
    library.unlink()
    assert build_portable.distribution_review(tmp_path)["passed"] is True
