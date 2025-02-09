from sqlalchemy import create_engine, text
from app import db

def get_unique_role_product_pairs(database_url: Optional[str] = None) -> List[Tuple[str, str]]:
    """Fetch unique role-product pairs from the importers table."""
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    engine = create_engine(database_url, pool_pre_ping=True)
    unique_pairs = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT role, product
            FROM importers
            WHERE role IS NOT NULL AND product IS NOT NULL
        """))

        for row in result:
            unique_pairs.append((row['role'], row['product']))

    return unique_pairs

# Example usage
if __name__ == "__main__":
    try:
        unique_roles_products = get_unique_role_product_pairs()
        for role, product in unique_roles_products:
            print(f"Role: {role}, Product: {product}")
    except Exception as e:
        print(f"Error: {e}")