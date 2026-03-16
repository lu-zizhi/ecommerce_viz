import pandas as pd
import os

files = os.listdir('data')
for f in files:
    if f.endswith('.csv'):
        try:
            df = pd.read_csv('data/' + f, nrows=2, encoding='utf-8')
        except:
            df = pd.read_csv('data/' + f, nrows=2, encoding='gbk')
        print(f'=== {f} ===')
        print(df.columns.tolist())
        print(df.head(2))
        print()