import sqlite3, pandas as pd
pd.set_option("display.width", 200) 
pd.set_option("display.max_columns", None)
con = sqlite3.connect("scimago.db")
print(pd.read_sql("SELECT * FROM v_issn_ano WHERE issn = '2157846X'", con))