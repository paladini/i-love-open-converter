from __future__ import annotations

import socket

from i_love_open_converter.pdf_ops import _abstractive_summary


def deny_network(*args, **kwargs):
    raise AssertionError("summary inference attempted network access")


socket.create_connection = deny_network
socket.socket.connect = deny_network

summary = _abstractive_summary(
    [
        "The self-hosted service processes documents on the local server.",
        "Its summarizer loads a compact language model stored in the container.",
    ]
)
if not summary:
    raise SystemExit("Local summary model did not produce a result")

print("SUMMARY_SMOKE_OK: local Python runtime loaded the model and generated text")
