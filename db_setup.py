import sqlite3
import os

def setup_database(db_path='aml_data.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open('schema.sql', 'r') as f:
        schema_sql = f.read()
    
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()
    print(f"Base de datos creada exitosamente en: {db_path}")

if __name__ == "__main__":
    setup_database()
