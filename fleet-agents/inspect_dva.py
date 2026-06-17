import pandas as pd

path = r"C:\Users\ayush.ai.srivastava\OneDrive - Accenture\Ayush Space\projects\metrolinx\Brampton's Vehicle Device Allocation File.xlsx"
df = pd.read_excel(path, dtype=str, nrows=5)
df.columns = [c.strip() for c in df.columns]
print("=== Columns ===")
for c in df.columns:
    print(repr(c))
print("\n=== First 5 rows ===")
print(df.to_string())
