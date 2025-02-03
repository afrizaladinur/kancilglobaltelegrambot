import csv
import logging
import os
from typing import Optional
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

def create_tables(engine) -> None:
    """Create required tables if they don't exist"""
    try:
        create_importers_sql = """
        CREATE TABLE IF NOT EXISTS importers (
            id SERIAL PRIMARY KEY,
            role VARCHAR(50),
            product VARCHAR(50),
            name VARCHAR(255) NOT NULL,
            country VARCHAR(100),
            phone VARCHAR(50),
            website TEXT,
            email_1 VARCHAR(255),
            email_2 VARCHAR(255),
            last_contact VARCHAR(100),
            status VARCHAR(50),
            wa_availability VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_processed_files_sql = """
        CREATE TABLE IF NOT EXISTS processed_files (
            id SERIAL PRIMARY KEY,
            file_path TEXT UNIQUE NOT NULL,
            row_count INTEGER NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        with engine.begin() as conn:
            conn.execute(text(create_importers_sql))
            conn.execute(text(create_processed_files_sql))
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}", exc_info=True)
        raise

def process_csv_row(row: dict) -> Optional[dict]:
    """Process and validate a single CSV row"""
    try:
        name = row.get("Name", "").strip()
        if not name:
            return None

        return {
            "role": row.get("Role", "").strip(),
            "product": row.get("Product", "").strip(),
            "name": name,
            "country": row.get("Country", "").strip(),
            "phone": row.get("Phone", "").strip(),
            "website": row.get("Website", "").strip(),
            "email_1": row.get("E-mail 1", "").strip(),
            "email_2": row.get("E-mail 2", "").strip(),
            "last_contact": row.get("Last Contact", "").strip(),
            "status": row.get("Status", "").strip(),
            "wa_availability": row.get("WA Availability", "Not Available").strip(),
        }
    except Exception as e:
        logger.error(f"Error processing row: {row}, Error: {str(e)}")
        return None

def import_csv_to_postgres(csv_file_path: str, database_url: Optional[str] = None) -> bool:
    """Import data from CSV file to PostgreSQL database"""
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        return False

    try:
        if database_url is None:
            database_url = os.environ.get("DATABASE_URL")
        
        engine = create_engine(database_url, pool_pre_ping=True)
        # Check if file was already processed
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM processed_files WHERE file_path = :path)"
            ), {"path": csv_file_path}).scalar()
            if result:
                logger.info(f"File {csv_file_path} was already processed, skipping")
                return True
        if database_url is None:
            database_url = os.environ.get("DATABASE_URL")
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")

        file_size = os.path.getsize(csv_file_path)
        logger.info(f"Processing file: {csv_file_path} (Size: {file_size} bytes)")

        engine = create_engine(database_url, pool_pre_ping=True)
        create_tables(engine)

        valid_rows = []
        with open(csv_file_path, "r", encoding="utf-8") as csvfile:
            csv_reader = csv.DictReader(csvfile)
            logger.info(f"CSV Headers: {csv_reader.fieldnames}")

            for i, row in enumerate(csv_reader, 1):
                processed_row = process_csv_row(row)
                if processed_row:
                    valid_rows.append(processed_row)
                    if len(valid_rows) % 100 == 0:
                        logger.info(f"Processed {len(valid_rows)} valid rows")

        if not valid_rows:
            logger.error("No valid data found in CSV file")
            return False

        logger.info(f"Found {len(valid_rows)} valid rows to import")

        # Insert data in a single transaction
        batch_size = 500
        inserted_count = 0

        with engine.begin() as conn:  # Single transaction block
            for batch_start in range(0, len(valid_rows), batch_size):
                batch = valid_rows[batch_start : batch_start + batch_size]

                insert_sql = """
                INSERT INTO importers (
                    role, product, name, country, phone, website,
                    email_1, email_2, last_contact, status, wa_availability
                ) VALUES (
                    :role, :product, :name, :country, :phone, :website,
                    :email_1, :email_2, :last_contact, :status, :wa_availability
                )
                """
                conn.execute(text(insert_sql), batch)
                inserted_count += len(batch)
                logger.info(f"Inserted batch of {len(batch)} rows. Total inserted: {inserted_count}")
            
            # Record the processed file
            track_file_sql = """
            INSERT INTO processed_files (file_path, row_count)
            VALUES (:file_path, :row_count)
            ON CONFLICT (file_path) DO NOTHING
            """
            conn.execute(text(track_file_sql), {
                "file_path": csv_file_path,
                "row_count": inserted_count
            })
            logger.info(f"Tracked file {csv_file_path} with {inserted_count} rows")

        # Verify final count
        with engine.connect() as conn:
            final_count = conn.execute(text("SELECT COUNT(*) FROM importers")).scalar()
            logger.info(f"Final row count in database: {final_count}")
            return final_count > 0

    except Exception as e:
        logger.error(f"Error importing CSV data: {str(e)}", exc_info=True)
        return False

def process_all_csv_files(data_dir: str = "data") -> bool:
    """Process all CSV files in the specified directory"""
    try:
        logger.info(f"Looking for CSV files in directory: {data_dir}")
        if not os.path.exists(data_dir):
            logger.error(f"Directory not found: {data_dir}")
            return False

        csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
        if not csv_files:
            logger.error(f"No CSV files found in {data_dir}")
            return False

        logger.info(f"Found CSV files: {csv_files}")
        success = True
        for csv_file in csv_files:
            file_path = os.path.join(data_dir, csv_file)
            logger.info(f"Processing file: {file_path}")
            if not import_csv_to_postgres(file_path):
                logger.error(f"Failed to import {file_path}")
                success = False
                break

        return success
    except Exception as e:
        logger.error(f"Error processing CSV files: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("Starting batch import process for all CSV files")
    if process_all_csv_files():
        logger.info("All CSV imports completed successfully")
        exit(0)
    else:
        logger.error("Some CSV imports failed")
        exit(1)
