#!/usr/bin/env python3

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Add new validation fields to the predictions table"""
    try:
        # Get database URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        # Fix for Render's PostgreSQL URL format
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Create engine
        engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"sslmode": "require"}
        )
        
        # Add new columns
        with engine.connect() as conn:
            # Add new columns if they don't exist
            conn.execute(text("""
                DO $$ 
                BEGIN
                    -- Add entry_hit if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='entry_hit') THEN
                        ALTER TABLE predictions ADD COLUMN entry_hit BOOLEAN DEFAULT FALSE;
                    END IF;
                    
                    -- Add entry_hit_time if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='entry_hit_time') THEN
                        ALTER TABLE predictions ADD COLUMN entry_hit_time TIMESTAMP;
                    END IF;
                    
                    -- Add tp_hit if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='tp_hit') THEN
                        ALTER TABLE predictions ADD COLUMN tp_hit BOOLEAN DEFAULT FALSE;
                    END IF;
                    
                    -- Add tp_hit_time if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='tp_hit_time') THEN
                        ALTER TABLE predictions ADD COLUMN tp_hit_time TIMESTAMP;
                    END IF;
                    
                    -- Add sl_hit if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='sl_hit') THEN
                        ALTER TABLE predictions ADD COLUMN sl_hit BOOLEAN DEFAULT FALSE;
                    END IF;
                    
                    -- Add sl_hit_time if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='sl_hit_time') THEN
                        ALTER TABLE predictions ADD COLUMN sl_hit_time TIMESTAMP;
                    END IF;
                    
                    -- Add validation_status if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='validation_status') THEN
                        ALTER TABLE predictions ADD COLUMN validation_status VARCHAR(20) DEFAULT 'PENDING';
                    END IF;
                    
                    -- Add validation_error if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                 WHERE table_name='predictions' AND column_name='validation_error') THEN
                        ALTER TABLE predictions ADD COLUMN validation_error VARCHAR(200);
                    END IF;
                END $$;
            """))
            
            conn.commit()
            logger.info("Database migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_database() 