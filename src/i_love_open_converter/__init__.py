"""I Love Open Converter application."""

import os

# Must be set before ONNX Runtime initializes, including in standalone workers.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
