import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile

def download_and_process_file(url, output_csv):
    # Download the file
    response = requests.get(url)
    if response.status_code == 200:
        with ZipFile(BytesIO(response.content)) as z:
            # Extract the file from the zip archive
            file_name = z.namelist()[0]
            with z.open(file_name) as f:
                # Read and process the file
                df = pd.read_csv(f, delimiter=',', engine='python')
                df['Expiry'] = pd.to_datetime(df['Expiry'])
                df['StrikePrice'] = df['StrikePrice'].astype(float)
                df.sort_values('Expiry', inplace=True)
                df.reset_index(drop=True, inplace=True)
                # Save to CSV
                df.to_csv(output_csv, index=False)
    else:
        print(f"Failed to download {url}")

# URLs and output files
urls_and_files = [
    ("https://api.shoonya.com/MCX_symbols.txt.zip", "/home/deep/Desktop/NEWshoonya/MCX_symbols.csv"),
    ("https://api.shoonya.com/NFO_symbols.txt.zip", "/home/deep/Desktop/NEWshoonya/NFO_symbols.csv"),
    ("https://api.shoonya.com/BFO_symbols.txt.zip", "/home/deep/Desktop/NEWshoonya/BFO_symbols.csv")
    
]

for url, output_csv in urls_and_files:
    download_and_process_file(url, output_csv)
