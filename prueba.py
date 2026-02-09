
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = 'aml_data.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

df = pd.read_sql_query("""SELECT t.* FROM transacciones t
    INNER JOIN caso_involucrados ci ON t.codunicocli_13_enc = ci.codunicocli_13_enc
    WHERE ci.id_caso = ? AND t.monto >= ? AND t.monto <= ? AND t.fecha >= ? AND t.fecha <= ?""", 
    get_connection(), params=[1, 0.0, 1000000.0, '2017-02-09', '2026-02-07'])

print(df)