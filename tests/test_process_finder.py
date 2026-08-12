import os
from src.network.process_finder import ProcessFinder

def test_get_current_process_name():
    current_pid = os.getpid()
    proc_name = ProcessFinder.get_process_name(current_pid)
    assert proc_name is not None
    assert "python" in proc_name.lower() or "pytest" in proc_name.lower()