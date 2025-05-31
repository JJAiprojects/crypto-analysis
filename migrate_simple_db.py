#!/usr/bin/env python3

import os
import psycopg2
from datetime import datetime

def migrate_to_simple_schema():
    """Migrate to simple prediction schema by dropping old complex table and creating new one"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    # Fix PostgreSQL URL format for newer psycopg2
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        print("🔌 Connecting to PostgreSQL database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Drop old complex table if it exists
        print("🗑️  Dropping old complex predictions table...")
        cursor.execute("DROP TABLE IF EXISTS predictions CASCADE;")
        
        # Create new simple predictions table
        print("📋 Creating new simple predictions table...")
        cursor.execute("""
            CREATE TABLE predictions (
                id SERIAL PRIMARY KEY,
                
                -- Basic timing info
                date VARCHAR(20) NOT NULL,
                time VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                
                -- Prediction method
                method VARCHAR(20) NOT NULL,  -- 'ai' or 'calculation'
                
                -- Core prediction data
                entry_level FLOAT NOT NULL,   -- Entry price
                stop_loss FLOAT NOT NULL,     -- Stop loss price  
                take_profit FLOAT NOT NULL,   -- Take profit price
                confidence FLOAT NOT NULL,    -- Confidence 0-100
                
                -- Validation field (filled later)
                accuracy FLOAT,               -- Actual accuracy (empty initially)
                
                -- Optional metadata
                coin VARCHAR(10) DEFAULT 'BTC',
                notes VARCHAR(500),
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validated_at TIMESTAMP
            );
        """)
        
        # Create useful indexes for performance
        print("🔍 Creating indexes...")
        cursor.execute("CREATE INDEX idx_predictions_date ON predictions(date);")
        cursor.execute("CREATE INDEX idx_predictions_method ON predictions(method);")
        cursor.execute("CREATE INDEX idx_predictions_timestamp ON predictions(timestamp);")
        
        # Commit changes
        conn.commit()
        
        # Verify table creation
        print("✅ Verifying table structure...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'predictions' 
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print("   New table columns:")
        for col in columns:
            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
            print(f"   - {col[0]} ({col[1]}) {nullable}")
        
        # Show row count (should be 0)
        cursor.execute("SELECT COUNT(*) FROM predictions;")
        count = cursor.fetchone()[0]
        print(f"   Total rows: {count}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database migration to simple schema completed successfully!")
        print("✅ Ready for new prediction system")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """Main migration function"""
    print("🔄 Simple Database Schema Migration")
    print("=" * 40)
    print("This will:")
    print("1. Drop the old complex predictions table")
    print("2. Create a new simple predictions table")
    print("3. Set up indexes for performance")
    print()
    
    # Show what we're migrating to
    print("📋 New simple schema:")
    schema_fields = [
        "id (primary key)",
        "date, time, timestamp (timing)",
        "method (ai/calculation)",
        "entry_level, stop_loss, take_profit (prices)",
        "confidence, accuracy (metrics)", 
        "coin, notes (metadata)",
        "created_at, validated_at (tracking)"
    ]
    
    for field in schema_fields:
        print(f"   ✓ {field}")
    
    print("\n" + "=" * 40)
    
    # Run migration
    success = migrate_to_simple_schema()
    
    if success:
        print("\n🚀 Migration complete! Your database is ready for the new system.")
        print("💡 Next steps:")
        print("   1. Deploy your cron job on Render")
        print("   2. Test with: python 6.py --test")
        print("   3. Check predictions in pgAdmin")
    else:
        print("\n❌ Migration failed. Check the error above.")

if __name__ == "__main__":
    main() 