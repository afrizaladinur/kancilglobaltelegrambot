import csv
import logging
import os
from typing import Optional
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def create_importers_table(engine) -> None:
    """Create the importers table if it doesn't exist"""
    try:
        # Drop existing table to ensure clean import
        drop_table_sql = """
        DROP TABLE IF EXISTS importers;
        """

        create_table_sql = """
        CREATE TABLE importers (
            id SERIAL PRIMARY KEY,
            role VARCHAR(50),
            product_code VARCHAR(50),
            name VARCHAR(255) NOT NULL,
            country VARCHAR(100),
            phone VARCHAR(50),
            website TEXT,
            email_1 VARCHAR(255),
            email_2 VARCHAR(255),
            last_contact DATE,
            status VARCHAR(50),
            wa_availability VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        with engine.connect() as conn:
            conn.execute(text(drop_table_sql))
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("Importers table created successfully")

    except Exception as e:
        logger.error(f"Error creating table: {str(e)}", exc_info=True)
        raise

def import_csv_to_postgres(csv_file_path: str, database_url: Optional[str] = None) -> bool:
    """Import data from CSV file to PostgreSQL database"""
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        return False

    try:
        if database_url is None:
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")

        logger.info(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
        engine = create_engine(database_url)

        # Create table
        create_importers_table(engine)

        # Process CSV file
        logger.info(f"Reading CSV file: {csv_file_path}")
        valid_rows = []

        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            next(csv_reader)  # Skip header row

            for i, row in enumerate(csv_reader, 2):  # Start from 2 since we skipped header
                try:
                    # Log raw data for debugging
                    logger.debug(f"Processing row {i}: {row}")

                    if not row or len(row) < 3:  # We expect at least role, code, and name
                        logger.warning(f"Row {i} has insufficient columns: {row}")
                        continue

                    data = {
                        'role': row[0],
                        'product_code': row[1],
                        'name': row[2],
                        'country': row[3] if len(row) > 3 else None,
                        'phone': row[4] if len(row) > 4 else None,
                        'website': row[5] if len(row) > 5 else None,
                        'email_1': row[6] if len(row) > 6 else None,
                        'email_2': row[7] if len(row) > 7 else None,
                        'status': row[9] if len(row) > 9 else None,
                        'wa_availability': row[10] if len(row) > 10 else None,
                        'last_contact': None
                    }

                    # Clean the data
                    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}
                    data = {k: (v if v else None) for k, v in data.items()}

                    if data['name']:  # Only include rows with a valid name
                        valid_rows.append(data)
                        if len(valid_rows) % 100 == 0:
                            logger.info(f"Processed {len(valid_rows)} valid rows")

                except Exception as e:
                    logger.error(f"Error processing row {i}: {str(e)}", exc_info=True)
                    continue

        if not valid_rows:
            logger.error("No valid data found in CSV file")
            return False

        logger.info(f"Found {len(valid_rows)} valid rows to import")

        # Insert data in batches
        insert_sql = """
        INSERT INTO importers (
            role, product_code, name, country, phone, website,
            email_1, email_2, last_contact, status,
            wa_availability
        ) VALUES (
            :role, :product_code, :name, :country, :phone, :website,
            :email_1, :email_2, :last_contact, :status,
            :wa_availability
        )
        """

        with engine.begin() as conn:
            for i, row in enumerate(valid_rows, 1):
                try:
                    conn.execute(text(insert_sql), row)
                    if i % 100 == 0:
                        logger.info(f"Inserted {i} rows")
                except Exception as e:
                    logger.error(f"Error inserting row {i}: {str(e)}", exc_info=True)
                    logger.error(f"Problematic row data: {row}")
                    raise

            logger.info(f"Successfully imported {len(valid_rows)} rows")
            return True

    except Exception as e:
        logger.error(f"Error importing CSV data: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    csv_file = "attached_assets/I - WW 0302.csv"  # Updated file path
    logger.info(f"Starting import process for {csv_file}")

    if import_csv_to_postgres(csv_file):
        logger.info("CSV import completed successfully")
    else:
        logger.error("CSV import failed")
        exit(1)