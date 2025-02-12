from sqlalchemy import create_engine, inspect, text

DATABASE_URL = "postgresql://neondb_owner:npg_L1SuFKwhdg0y@ep-frosty-silence-a6853ovp.us-west-2.aws.neon.tech/neondb?sslmode=require"

engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_size=5,
    max_overflow=10
)
# Get inspector
inspector = inspect(engine)

# Get columns for saved_contacts table
columns = inspector.get_columns('importers')

# Print column details
for column in columns:
    print(f"Column: {column['name']}")
    print(f"Type: {column['type']}")
    print(f"Nullable: {column['nullable']}")
    print("---")

# Count the number of rows in saved_contacts table
with engine.connect() as connection:
    result = connection.execute(text("""SELECT DISTINCT "wa_availability", COUNT(*) 
FROM importers 
GROUP BY "wa_availability" """))
    row_count = sum(row[1] for row in result)
    print(f"Number of rows in saved_contacts table: {row_count}")