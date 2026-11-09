# SPDX-License-Identifier: Apache-2.0
"""Lightweight factory for the optional LMCache-Ascend HIXL backend."""

# Future
from __future__ import annotations

# Standard
from typing import TYPE_CHECKING

# First Party
from lmcache.v1.distributed.transfer_channel.factory import (
    register_transfer_channel_factory,
)

if TYPE_CHECKING:
    # First Party
    from lmcache.v1.distributed.internal_api import L1MemoryDesc
    from lmcache.v1.distributed.transfer_channel.abstract import TransferChannelContext


def create_hixl_transfer_channel_context(
    l1_memory_desc: L1MemoryDesc,
    listen_url: str,
    advertise_url: str,
    **kwargs: object,
) -> TransferChannelContext:
    """Load the Ascend implementation on selection and create its Context.

    Args:
        l1_memory_desc: Local L1 region, passed unchanged to the backend.
        listen_url: Channel metadata server's bind address (host:port).
        advertise_url: Channel metadata address advertised to peers (host:port).
        **kwargs: Accepted for factory compatibility; unused by HIXL. Backend
            options are configured by LMCache-Ascend through environment variables.

    Returns:
        A new Context owned by the caller or the public global lifecycle.

    Raises:
        RuntimeError: The optional Ascend backend cannot be imported; the
            original ImportError or OSError is retained as the cause.

    Note:
        Backend construction errors propagate unchanged. Importing this factory
        to register it does not import LMCache-Ascend or the native HIXL binding.
    """
    try:
        # Third Party
        from lmcache_ascend.v1.mp_hixl_channel import HixlTransferChannelContext
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Failed to load the LMCache-Ascend HIXL backend; "
            "install a compatible LMCache-Ascend package to use 'hixl'"
        ) from exc

    return HixlTransferChannelContext(
        l1_memory_desc=l1_memory_desc,
        listen_url=listen_url,
        advertise_url=advertise_url,
    )


register_transfer_channel_factory("hixl", create_hixl_transfer_channel_context)
