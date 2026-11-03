import sqlite3
import pandas as pd
from pathlib import Path

def init_db(data_dir: str = "data") -> sqlite3.Connection:
    """
    Initializes an in-memory SQLite database, loads operational CSV files,
    ensures all ID columns are cast to string, and uploads them to RAM.
    """
    # 1. Create a connection to an in-memory database (stored in RAM)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    data_path = Path(data_dir)
    
    tables = [
        "categories",
        "customers",
        "products",
        "orders",
        "order_items",
        "promotions"
    ]
    
    # List of known ID columns to force as strings
    id_columns = ["category_id", "customer_id", "product_id", "order_id", "promotion_id"]
    
    for table in tables:
        csv_file = data_path / f"{table}.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            
            # Clean column names (remove extra whitespace)
            df.columns = df.columns.str.strip()
            
            # Convert all ID columns (or columns ending with '_id') to string
            for col in df.columns:
                if col in id_columns or col.endswith("_id"):
                    df[col] = df[col].astype(str)
            
            # Load DataFrame into SQLite in-memory table
            df.to_sql(table, conn, index=False, if_exists="replace")
        else:
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
            
    return conn


def validate_db(conn: sqlite3.Connection) -> None:
    """
    Performs a single, consolidated sanity check on loaded tables:
    displays row count, column count, column names, and their SQLite data types.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("\n" + "="*70)
    print("           DATABASE IN-MEMORY VALIDATION SUMMARY")
    print("="*70)
    
    for table in tables:
        # Get total row count
        row_count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
        # Get column info: PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
        cursor.execute(f"PRAGMA table_info({table});")
        col_info = cursor.fetchall()
        col_count = len(col_info)
        
        # Format column details as 'column_name (TYPE)'
        col_details = [f"{col[1]} ({col[2]})" for col in col_info]
        
        print(f"\nTable: '{table}'")
        print(f"  - Rows: {row_count} | Columns: {col_count}")
        print(f"  - Schema & Data Types: {', '.join(col_details)}")
        
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    db = init_db()
    validate_db(db)