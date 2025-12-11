import sys
import os
sys.path.append(os.getcwd())
try:
    from logger.fast_logger import FastLogger
    print("FastLogger imported successfully")
    l = FastLogger()
    print(f"Created logger: {l.filename}")
    l.close()
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Error: {e}")

