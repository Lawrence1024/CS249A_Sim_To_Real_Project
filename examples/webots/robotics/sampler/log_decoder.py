import pandas as pd
import struct

class LogDecoder:

    @staticmethod
    def decode_df(filename: str):
        '''
        Decodes the binary file and save as pandas dataframe
        '''

        struct_fmt = '<dI3f4fi'
        struct_size = struct.calcsize(struct_fmt)
        df = None
        with open(filename, 'rb') as f:
            data_rows = []
            while True:
                bytes_read = f.read(struct_size)
                if not bytes_read:
                    break
                data_rows.append(struct.unpack(struct_fmt, bytes_read))

        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=['timestamp', 
                                              'step_count', 
                                              'x', 'y', 'z', 
                                              'heading', 'targetHeading', 
                                              'effectiveHHeading', 'angle', 
                                              'target_id'])
        return df
        
    @staticmethod
    def decode_csv(filename: str):
        '''
        Decodes the binary file and save as csv format
        '''
        df = LogDecoder.decode_df(filename)
        if df is None:
            return
        csv_filename = filename.rsplit('.', 1)[0] + '.csv'
        df.to_csv(csv_filename, index=False)

    @staticmethod
    def decode_parquet(filename: str):
        '''
        Decodes the binary file and save as parquet format
        '''
        df = LogDecoder.decode_df(filename)
        if df is None:
            return
        parquet_filename = filename.rsplit('.', 1)[0] + '.parquet'
        df.to_parquet(parquet_filename, index=False)

    @staticmethod
    def decode_txt(filename: str):
        '''
        Decodes the binary file and save as txt format
        '''
        df = LogDecoder.decode_df(filename)
        if df is None:
            return
        txt_filename = filename.rsplit('.', 1)[0] + '.txt'
        df.to_csv(txt_filename, index=False, sep='\t')


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python log_decoder.py <binary_log_file>")
        sys.exit(1)

    binary_log_file = sys.argv[1]
    LogDecoder.decode_csv(binary_log_file)
    LogDecoder.decode_parquet(binary_log_file)
    LogDecoder.decode_txt(binary_log_file)