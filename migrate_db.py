#!/usr/bin/env python3

import os
import logging
import json
from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.dialects.postgresql import JSONB

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_connection():
    """Get database connection with proper error handling"""
    try:
        # Get database URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return None
            
        # Fix for Render's PostgreSQL URL format
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Create engine with enhanced settings
        engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"sslmode": "require"}
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
        
        return engine
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def check_table_exists(engine, table_name):
    """Check if a table exists in the database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                );
            """))
            exists = result.fetchone()[0]
            logger.info(f"Table '{table_name}' exists: {exists}")
            return exists
    except Exception as e:
        logger.error(f"Error checking table existence: {e}")
        return False

def create_predictions_table(engine):
    """Create the predictions table with all necessary fields"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    date VARCHAR(20) NOT NULL,
                    session VARCHAR(20) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    
                    -- Market data fields
                    btc_price FLOAT,
                    eth_price FLOAT,
                    btc_rsi FLOAT,
                    eth_rsi FLOAT,
                    fear_greed INTEGER,
                    
                    -- Prediction data (JSON)
                    predictions_data JSON NOT NULL,
                    
                    -- AI prediction text
                    ai_prediction TEXT,
                    
                    -- Professional analysis (JSON)
                    professional_analysis JSON,
                    
                    -- ML predictions (JSON)
                    ml_predictions JSON,
                    
                    -- Risk analysis (JSON)
                    risk_analysis JSON,
                    
                    -- Validation data
                    validation_points JSON DEFAULT '[]'::json,
                    final_accuracy FLOAT,
                    
                    -- Processing flags
                    ml_processed BOOLEAN DEFAULT FALSE,
                    hourly_validated BOOLEAN DEFAULT FALSE,
                    last_validation TIMESTAMP,
                    
                    -- Enhanced fields for validation learning
                    trade_metrics JSON,
                    
                    -- New fields for detailed validation
                    entry_hit BOOLEAN DEFAULT FALSE,
                    entry_hit_time TIMESTAMP,
                    tp_hit BOOLEAN DEFAULT FALSE,
                    tp_hit_time TIMESTAMP,
                    sl_hit BOOLEAN DEFAULT FALSE,
                    sl_hit_time TIMESTAMP,
                    validation_status VARCHAR(20) DEFAULT 'PENDING',
                    validation_error VARCHAR(200),
                    
                    -- Additional metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create indexes for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_predictions_date_session ON predictions(date, session);
                CREATE INDEX IF NOT EXISTS idx_predictions_validation_status ON predictions(validation_status);
                CREATE INDEX IF NOT EXISTS idx_predictions_hourly_validated ON predictions(hourly_validated);
            """))
            
            conn.commit()
            logger.info("✅ Predictions table created successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to create predictions table: {e}")
        return False

def create_learning_insights_table(engine):
    """Create the learning_insights table"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_insights (
                    id SERIAL PRIMARY KEY,
                    insight_type VARCHAR(50) NOT NULL,
                    period VARCHAR(50),
                    data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_learning_insights_type ON learning_insights(insight_type);
                CREATE INDEX IF NOT EXISTS idx_learning_insights_period ON learning_insights(period);
                CREATE INDEX IF NOT EXISTS idx_learning_insights_created ON learning_insights(created_at);
            """))
            
            conn.commit()
            logger.info("✅ Learning insights table created successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to create learning insights table: {e}")
        return False

def migrate_existing_columns(engine):
    """Add new columns to existing predictions table"""
    try:
        with engine.connect() as conn:
            # Check existing columns first
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'predictions'
            """))
            existing_columns = {row[0] for row in result.fetchall()}
            logger.info(f"Existing columns: {sorted(existing_columns)}")
            
            # Define all required columns with their SQL types
            required_columns = {
                'ai_prediction': 'TEXT',
                'professional_analysis': 'JSON',
                'ml_predictions': 'JSON',
                'risk_analysis': 'JSON',
                'entry_hit': 'BOOLEAN DEFAULT FALSE',
                'entry_hit_time': 'TIMESTAMP',
                'tp_hit': 'BOOLEAN DEFAULT FALSE',
                'tp_hit_time': 'TIMESTAMP',
                'sl_hit': 'BOOLEAN DEFAULT FALSE',
                'sl_hit_time': 'TIMESTAMP',
                'validation_status': 'VARCHAR(20) DEFAULT \'PENDING\'',
                'validation_error': 'VARCHAR(200)',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Add missing columns
            added_columns = []
            for column_name, column_type in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        conn.execute(text(f"""
                            ALTER TABLE predictions 
                            ADD COLUMN {column_name} {column_type};
                        """))
                        added_columns.append(column_name)
                        logger.info(f"✅ Added column: {column_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to add column {column_name}: {e}")
            
            # Create/update indexes
            index_queries = [
                "CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp);",
                "CREATE INDEX IF NOT EXISTS idx_predictions_date_session ON predictions(date, session);",
                "CREATE INDEX IF NOT EXISTS idx_predictions_validation_status ON predictions(validation_status);",
                "CREATE INDEX IF NOT EXISTS idx_predictions_hourly_validated ON predictions(hourly_validated);"
            ]
            
            for query in index_queries:
                try:
                    conn.execute(text(query))
                except Exception as e:
                    logger.warning(f"⚠️ Index creation warning: {e}")
            
            conn.commit()
            
            if added_columns:
                logger.info(f"✅ Migration completed successfully. Added {len(added_columns)} columns: {added_columns}")
            else:
                logger.info("✅ All columns already exist. No migration needed.")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def validate_database_schema(engine):
    """Validate that all required fields are present"""
    try:
        with engine.connect() as conn:
            # Get current schema
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'predictions'
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            logger.info("📋 Current database schema:")
            for col in columns:
                logger.info(f"  {col[0]} ({col[1]}) - Nullable: {col[2]} - Default: {col[3]}")
            
            # Check for required core fields
            required_core_fields = [
                'id', 'date', 'session', 'timestamp', 'btc_price', 'eth_price',
                'predictions_data', 'validation_points', 'entry_hit', 'tp_hit',
                'sl_hit', 'validation_status'
            ]
            
            column_names = {col[0] for col in columns}
            missing_fields = [field for field in required_core_fields if field not in column_names]
            
            if missing_fields:
                logger.error(f"❌ Missing required fields: {missing_fields}")
                return False
            else:
                logger.info("✅ All required fields are present")
                return True
                
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        return False

def backup_existing_data(engine):
    """Create a backup of existing data before migration"""
    try:
        with engine.connect() as conn:
            # Check if there's any data to backup
            result = conn.execute(text("SELECT COUNT(*) FROM predictions"))
            row_count = result.fetchone()[0]
            
            if row_count > 0:
                logger.info(f"📦 Found {row_count} existing records")
                
                # Create backup table
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_table = f"predictions_backup_{timestamp}"
                
                conn.execute(text(f"""
                    CREATE TABLE {backup_table} AS 
                    SELECT * FROM predictions;
                """))
                
                logger.info(f"✅ Created backup table: {backup_table}")
                return True
            else:
                logger.info("📦 No existing data to backup")
                return True
                
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        return False

def migrate_database():
    """Main migration function with comprehensive error handling"""
    logger.info("🚀 Starting database migration...")
    
    # Get database connection
    engine = get_database_connection()
    if not engine:
        return False
    
    try:
        # Check if predictions table exists
        predictions_exist = check_table_exists(engine, 'predictions')
        
        if predictions_exist:
            logger.info("📋 Predictions table exists, performing column migration...")
            
            # Backup existing data
            if not backup_existing_data(engine):
                logger.warning("⚠️ Backup failed, but continuing with migration...")
            
            # Migrate existing columns
            if not migrate_existing_columns(engine):
                logger.error("❌ Column migration failed")
                return False
        else:
            logger.info("📋 Predictions table doesn't exist, creating new table...")
            
            # Create new table
            if not create_predictions_table(engine):
                logger.error("❌ Table creation failed")
                return False
        
        # Create learning insights table
        if not check_table_exists(engine, 'learning_insights'):
            if not create_learning_insights_table(engine):
                logger.warning("⚠️ Learning insights table creation failed")
        
        # Validate schema
        if not validate_database_schema(engine):
            logger.error("❌ Schema validation failed")
            return False
        
        # Final connection test
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM predictions"))
            record_count = result.fetchone()[0]
            logger.info(f"📊 Database has {record_count} prediction records")
        
        logger.info("🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed with error: {e}")
        return False
    finally:
        engine.dispose()

def run_local_migration():
    """Run migration for local SQLite database to match remote format"""
    logger.info("🏠 Running local database migration...")
    
    try:
        # Import database manager to initialize local database
        from database_manager import DatabaseManager
        
        db_manager = DatabaseManager()
        if db_manager.use_database:
            logger.info("✅ Local database initialized successfully")
            
            # Check if it's SQLite (local) or PostgreSQL (remote)
            if 'sqlite' in str(db_manager.engine.url):
                logger.info("🗄️ Local SQLite database detected")
                
                # For SQLite, we need to ensure all columns exist
                # The DatabaseManager should handle this through SQLAlchemy
                with db_manager.get_session() as session:
                    result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'"))
                    if result.fetchone():
                        logger.info("✅ Local predictions table exists")
                    else:
                        logger.info("📋 Local predictions table will be created by SQLAlchemy")
                
                # Test a basic operation
                test_prediction = {
                    "date": "2025-01-01",
                    "session": "test",
                    "timestamp": datetime.now().isoformat(),
                    "market_data": {"btc_price": 100000, "eth_price": 4000},
                    "ai_prediction": "Test prediction",
                    "professional_analysis": {"test": True},
                    "validation_status": "PENDING"
                }
                
                # Try saving and removing test prediction
                success = db_manager.save_prediction(test_prediction)
                if success:
                    logger.info("✅ Local database format validation successful")
                else:
                    logger.warning("⚠️ Local database test failed")
            else:
                logger.info("🌐 Remote PostgreSQL database detected")
        else:
            logger.warning("⚠️ Local database not available, using JSON fallback")
            
    except Exception as e:
        logger.error(f"❌ Local migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        # Run local migration
        success = run_local_migration()
    else:
        # Run remote migration
        success = migrate_database()
    
    if success:
        logger.info("✅ Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed!")
        sys.exit(1) 