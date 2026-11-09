# SPDX-License-Identifier: Apache-2.0
"""Check the optional Ascend backend through the public context lifecycle."""

# Standard
from pathlib import Path
import os
import subprocess
import sys
import textwrap


def _run_probe(tmp_path: Path, backend_source: str, script: str) -> None:
    """Run real factory discovery with an isolated optional backend package."""
    package = tmp_path / "lmcache_ascend"
    (package / "v1").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "v1/__init__.py").write_text("", encoding="utf-8")
    (package / "v1/mp_hixl_channel.py").write_text(
        textwrap.dedent(backend_source), encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path), *filter(None, [env.get("PYTHONPATH")])]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_discovery_does_not_import_ascend(tmp_path: Path) -> None:
    """Factory discovery must not activate the optional backend package."""
    _run_probe(
        tmp_path,
        'raise AssertionError("Unselected HIXL backend imported")',
        """
        import sys
        from lmcache.v1.distributed.transfer_channel import (
            initialize_transfer_channel_context,
        )
        assert callable(initialize_transfer_channel_context)
        assert "lmcache_ascend" not in sys.modules
        assert "lmcache_ascend.hixl_npu_comms" not in sys.modules
        """,
    )


def test_selected_hixl_forwards_parameters_and_closes(tmp_path: Path) -> None:
    """The factory forwards public arguments and leaves ownership to lifecycle."""
    _run_probe(
        tmp_path,
        """
        class HixlTransferChannelContext:
            def __init__(self, l1_memory_desc, listen_url, advertise_url):
                self.received = (l1_memory_desc, listen_url, advertise_url)
                self.closed = False
            def close(self):
                self.closed = True
        """,
        """
        from lmcache.v1.distributed.internal_api import L1MemoryDesc
        from lmcache.v1.distributed.transfer_channel import (
            initialize_transfer_channel_context, get_transfer_channel_context,
            delete_transfer_channel_context,
        )
        desc = L1MemoryDesc(ptr=4099, size=8192, align_bytes=4096)
        context = initialize_transfer_channel_context(
            "hixl", desc, "0.0.0.0:7600", "10.0.0.1:7600",
            backends=["unused"],
        )
        assert context.received[0] is desc
        assert context.received[1:] == ("0.0.0.0:7600", "10.0.0.1:7600")
        assert get_transfer_channel_context() is context
        delete_transfer_channel_context()
        assert context.closed
        """,
    )


def test_selected_hixl_chains_backend_import_error(tmp_path: Path) -> None:
    """Selection reports a missing dependency without publishing a Context."""
    _run_probe(
        tmp_path,
        'raise ModuleNotFoundError("Missing Ascend dependency", name="ascend_dep")',
        """
        from lmcache.v1.distributed.internal_api import L1MemoryDesc
        from lmcache.v1.distributed.transfer_channel import (
            initialize_transfer_channel_context, get_transfer_channel_context,
        )
        try:
            initialize_transfer_channel_context(
                "hixl", L1MemoryDesc(4096, 4096, 4096), "host:7600", "host:7600",
            )
        except RuntimeError as error:
            assert "LMCache-Ascend HIXL backend" in str(error)
            assert isinstance(error.__cause__, ModuleNotFoundError)
            assert error.__cause__.name == "ascend_dep"
        else:
            raise AssertionError("Missing backend was accepted")
        try:
            get_transfer_channel_context()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Failed import published a Context")
        """,
    )


def test_constructor_error_is_not_reclassified_as_loading_error(tmp_path: Path) -> None:
    """Only the import is wrapped, even when construction raises ImportError."""
    _run_probe(
        tmp_path,
        """
        error = ImportError("constructor dependency failure")
        class HixlTransferChannelContext:
            def __init__(self, **kwargs):
                raise error
        """,
        """
        from lmcache.v1.distributed.internal_api import L1MemoryDesc
        from lmcache.v1.distributed.transfer_channel import (
            initialize_transfer_channel_context,
        )
        try:
            initialize_transfer_channel_context(
                "hixl", L1MemoryDesc(4096, 4096, 4096), "host:7600", "host:7600",
            )
        except ImportError as error:
            from lmcache_ascend.v1.mp_hixl_channel import error as original
            assert error is original
        else:
            raise AssertionError("Constructor error was swallowed")
        """,
    )
