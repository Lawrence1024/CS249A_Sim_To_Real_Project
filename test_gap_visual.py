import importlib.util
import sys
import types
from pathlib import Path

SAMPLER_DIR = Path(__file__).resolve().parent / "examples/webots/robotics/sampler"

# Load the local log_decoder.py (lives beside gap_analyzer_v2.py)
log_decoder_path = SAMPLER_DIR / "log_decoder.py"
spec = importlib.util.spec_from_file_location("log_decoder", log_decoder_path)
log_decoder = importlib.util.module_from_spec(spec) if spec and spec.loader else None
if spec and spec.loader and log_decoder:
    spec.loader.exec_module(log_decoder)
    # Expose as both top-level and logger.log_decoder to satisfy gap_analyzer_v2 import
    sys.modules["log_decoder"] = log_decoder
    logger_pkg = types.ModuleType("logger")
    logger_pkg.log_decoder = log_decoder
    sys.modules["logger"] = logger_pkg
    sys.modules["logger.log_decoder"] = log_decoder
else:
    raise ImportError(f"Could not load log_decoder from {log_decoder_path}")

from examples.webots.robotics.sampler import gap_analyzer_v2 as ga2
from log_decoder import LogDecoder

df_sim = LogDecoder.decode_df("examples/webots/robotics/log/fast_log_1765339274_work.bin")
df_real = LogDecoder.decode_df("examples/webots/robotics/log/fast_log_1765338151_fail.bin")

ga2.visualize_gap_over_time(df_sim, df_real, use_relative_deltas=False)
# or for motion-delta mode:
ga2.visualize_gap_over_time(df_sim, df_real, use_relative_deltas=True)