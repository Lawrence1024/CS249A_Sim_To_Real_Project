from examples.webots.robotics.sampler import gap_analyzer_v2 as ga2
from logger.log_decoder import LogDecoder

df_sim = LogDecoder.decode_df("examples/webots/robotics/log/fast_log_1765339274_work.bin")
df_real = LogDecoder.decode_df("examples/webots/robotics/log/fast_log_1765338151_fail.bin")

ga2.visualize_gap_over_time(df_sim, df_real, use_relative_deltas=False)
# or for motion-delta mode:
ga2.visualize_gap_over_time(df_sim, df_real, use_relative_deltas=True)