import csv
import logging
import os
from typing import List, Optional
from sqlalchemy import create_engine, text
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed to DEBUG for more detailed logs
)
logger = logging.getLogger(__name__)

def create_importers_table(engine) -> None:
    """Create the importers table if it doesn't exist"""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS importers (
        id SERIAL PRIMARY KEY,
        role VARCHAR(50),
        product VARCHAR(50),
        name VARCHAR(255) NOT NULL,
        country VARCHAR(100),
        phone VARCHAR(50),
        website TEXT,
        email_1 VARCHAR(255) NULL,
        email_2 VARCHAR(255) NULL,
        last_contact DATE NULL,
        status VARCHAR(50),
        wa_availability VARCHAR(50),
        email_sent VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
        logger.info("importers table created or already exists")

def map_csv_columns(row: dict) -> dict:
    """Map CSV columns to database columns"""
    column_mapping = {
        'Role': 'role',
        'Product': 'product',
        'Name': 'name',
        'Country': 'country',
        'Phone': 'phone',
        'Website': 'website',
        'E-mail 1': 'email_1',
        'E-mail 2': 'email_2',
        'Last Contact': 'last_contact',
        'Status': 'status',
        'WA Availability': 'wa_availability',
        'E-mail Sent': 'email_sent'
    }

    return {
        column_mapping.get(k, k.lower().replace(' ', '_')): (v.strip() if v and v.strip() else None)
        for k, v in row.items()
    }

def import_csv_to_postgres(
    csv_file_path: str,
    database_url: Optional[str] = None
) -> bool:
    """
    Import data from CSV file to PostgreSQL database
    Returns True if successful, False otherwise
    """
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        return False

    try:
        # Use the DATABASE_URL from environment if not provided
        if database_url is None:
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")

        logger.debug(f"Connecting to database...")
        engine = create_engine(database_url)

        # Create table if it doesn't exist
        create_importers_table(engine)

        logger.info(f"Reading CSV file: {csv_file_path}")
        # Read and process CSV file
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            rows = []
            for i, row in enumerate(csv_reader, 1):
                try:
                    processed_row = map_csv_columns(row)
                    rows.append(processed_row)
                    if i % 1000 == 0:  # Log progress every 1000 rows
                        logger.debug(f"Processed {i} rows from CSV")
                except Exception as e:
                    logger.error(f"Error processing row {i}: {str(e)}")
                    continue

        if not rows:
            logger.warning("No data found in CSV file")
            return False

        logger.info(f"Found {len(rows)} rows to import")

        # Insert data using SQLAlchemy
        insert_sql = """
        INSERT INTO importers (
            role, product, name, country, phone, website,
            email_1, email_2, last_contact, status,
            wa_availability, email_sent
        ) VALUES (
            :role, :product, :name, :country, :phone, :website,
            :email_1, :email_2, :last_contact, :status,
            :wa_availability, :email_sent
        )
        """

        with engine.connect() as conn:
            inserted_count = 0
            for i, row in enumerate(rows, 1):
                try:
                    # Convert date string to proper format if it exists
                    if row.get('last_contact'):
                        try:
                            date_str = row['last_contact']
                            # Try different date formats
                            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                                try:
                                    parsed_date = datetime.strptime(date_str, fmt)
                                    row['last_contact'] = parsed_date.date()
                                    break
                                except ValueError:
                                    continue
                        except Exception as e:
                            logger.warning(f"Could not parse date {row['last_contact']}: {e}")
                            row['last_contact'] = None

                    conn.execute(text(insert_sql), row)
                    inserted_count += 1

                    if i % 1000 == 0:  # Commit every 1000 rows
                        conn.commit()
                        logger.debug(f"Inserted {i} rows")
                except Exception as e:
                    logger.error(f"Error inserting row {i}: {str(e)}")
                    logger.debug(f"Problematic row data: {row}")
                    continue

            conn.commit()  # Final commit for remaining rows

        logger.info(f"Successfully imported {inserted_count} rows to importers table")
        return True

    except Exception as e:
        logger.error(f"Error importing CSV data: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Import the new WW 0303 CSV file
    csv_file = "attached_assets/I - WW 0303.csv"
    logger.info(f"Starting import process for {csv_file}")
    if import_csv_to_postgres(csv_file):
        print("CSV import completed successfully")
    else:
        print("CSV import failed")