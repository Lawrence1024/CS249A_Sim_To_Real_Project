import threading
import queue
import time
import struct

class FastLogger:
    def __init__(self, filename = None, flush_interval=0.1):
        self.q = queue.Queue()
        self.flush_interval = flush_interval
        if filename is None:
            timestamp = int(time.time())
            filename = f'fast_log_{timestamp}.bin'
        self.filename = filename
        self.stop_flag = False
        
        # 'ab' = Append Binary.
        self.file = open(self.filename, 'ab') 
        
        # Format: < (Little Endian), d (double), I (uint), 3f (3 floats), 4f (4 floats), i (int)
        # Total size: 8 + 4 + 12 + 16 + 4 = 44 bytes
        self.struct_fmt = '<dI3f4fi'
        
        self.thread = threading.Thread(target=self._writer_thread, daemon=True)
        self.thread.start()

    def __del__(self):
        self.close()

    def log(self, timestamp: float, step_count: int, pos: tuple, quat: tuple, target_id: int):
        """
        Accepts raw arguments.
        pos: tuple/list of (x, y, z)
        quat: tuple/list of (qx, qy, qz, qw)
        """
        # We pack data into a tuple immediately to ensure immutability in the queue
        data_tuple = (timestamp, step_count, *pos, *quat, target_id)
        
        try:
            self.q.put(data_tuple, block=False)
        except queue.Full:
            pass

    def _writer_thread(self):
        byte_buffer = bytearray()
        last_flush = time.time()

        while not self.stop_flag or not self.q.empty():
            try:
                item = self.q.get(timeout=0.01)
                
                # Pack binary data. This is extremely fast (< 1us)
                byte_buffer.extend(struct.pack(self.struct_fmt, *item))
                
            except queue.Empty:
                pass

            now = time.time()
            # Flush if time elapsed or buffer > 4KB (standard page size)
            if (now - last_flush >= self.flush_interval) or (len(byte_buffer) >= 4096):
                if byte_buffer:
                    self._flush_buffer(byte_buffer)
                    byte_buffer.clear() # Reset buffer
                last_flush = now

        # Final flush
        if byte_buffer:
            self._flush_buffer(byte_buffer)

    def _flush_buffer(self, buffer):
        self.file.write(buffer)
        self.file.flush()
        # os.fsync(self.file.fileno()) # Uncomment if you fear power loss

    def close(self):
        self.stop_flag = True
        self.thread.join()
        self.file.close()