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
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS importers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            country VARCHAR(100),
            phone VARCHAR(50),
            website TEXT,
            email_1 VARCHAR(255),
            email_2 VARCHAR(255),
            product VARCHAR(50),
            product_description TEXT,
            wa_availability VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        with engine.connect() as conn:
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
            # Read and log the first few lines to debug
            logger.info("First few lines of CSV:")
            for i, line in enumerate(csvfile):
                if i < 5:  # Log first 5 lines
                    logger.info(f"Line {i}: {line.strip()}")
                else:
                    break
            csvfile.seek(0)  # Reset file pointer to start

            csv_reader = csv.DictReader(csvfile)
            logger.info(f"CSV Headers: {csv_reader.fieldnames}")

            for i, row in enumerate(csv_reader, 1):
                try:
                    # Log raw data for debugging
                    logger.debug(f"Processing row {i}: {row}")

                    # Skip empty rows
                    if not any(row.values()):
                        logger.debug(f"Skipping empty row {i}")
                        continue

                    data = {
                        'name': row.get('company_name', '').strip(),
                        'country': row.get('country_of_origin', '').strip(),
                        'product': row.get('hs_code', '').strip(),
                        'product_description': row.get('product_description', '').strip(),
                        'wa_availability': 'Available',  # Default to available for demo
                        'phone': '',  # These fields are not in the CSV but required by the schema
                        'website': '',
                        'email_1': '',
                        'email_2': ''
                    }

                    # Log processed data
                    logger.debug(f"Processed data for row {i}: {data}")

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

        # Insert data in smaller batches with explicit transaction
        batch_size = 50
        inserted_count = 0

        try:
            with engine.connect() as conn:
                # First, clear existing data
                conn.execute(text("TRUNCATE TABLE importers RESTART IDENTITY;"))
                conn.commit()

                for batch_start in range(0, len(valid_rows), batch_size):
                    batch = valid_rows[batch_start:batch_start + batch_size]

                    # Start transaction for this batch
                    with conn.begin():
                        for row in batch:
                            insert_sql = """
                            INSERT INTO importers (
                                name, country, phone, website,
                                email_1, email_2, product, product_description,
                                wa_availability
                            ) VALUES (
                                :name, :country, :phone, :website,
                                :email_1, :email_2, :product, :product_description,
                                :wa_availability
                            )
                            """
                            conn.execute(text(insert_sql), row)

                        inserted_count += len(batch)
                        logger.info(f"Inserted batch of {len(batch)} rows. Total inserted: {inserted_count}")

                logger.info(f"Successfully imported all {inserted_count} rows")

                # Verify the import
                result = conn.execute(text("SELECT COUNT(*) FROM importers")).scalar()
                logger.info(f"Total rows in database after import: {result}")

                return True

        except Exception as e:
            logger.error(f"Error during batch insert: {str(e)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error importing CSV data: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    csv_file = "trade_data.csv"
    logger.info(f"Starting import process for {csv_file}")

    if import_csv_to_postgres(csv_file):
        logger.info("CSV import completed successfully")
    else:
        logger.error("CSV import failed")
        exit(1)