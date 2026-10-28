"""The engine must not outlive the desktop shell that started it."""
import os
import subprocess
import sys
import time

from hypothesislab.desktop import parent_alive, watch_parent


def test_parent_alive_for_our_own_parent_and_not_for_a_dead_child():
    assert parent_alive(os.getppid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    # A reaped child is gone; a random huge pid does not exist either.
    assert not parent_alive(child.pid) or os.getppid() != child.pid
    assert not parent_alive(2_000_000_000)


def test_watch_parent_calls_exit_when_the_parent_is_gone():
    calls = []
    watch_parent(2_000_000_000, interval=0.05, exit_fn=lambda code: calls.append(code))
    deadline = time.time() + 2
    while not calls and time.time() < deadline:
        time.sleep(0.05)
    time.sleep(0.15)  # a returning test exit must terminate the watchdog too
    assert calls == [0]
