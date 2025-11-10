import pandas as pd
import sqlite3


df = pd.read_excel('doctors_db.xlsx', sheet_name="Sheet3")
print(df)

conn = sqlite3.connect('db/models/pharmacy.db')
cursor = conn.cursor()

df.to_sql("main_specs", conn, if_exists="append", index=False)
conn.commit()

for row in cursor.execute("SELECT * FROM main_specs"):
    print(row)