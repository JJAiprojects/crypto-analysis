import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class PredictionRecord(Base):
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True)
    
    # Basic info
    date = Column(String(20), nullable=False)  # 2025-05-30
    time = Column(String(20), nullable=False)  # 10:30
    timestamp = Column(DateTime, nullable=False)
    
    # Prediction method
    method = Column(String(20), nullable=False)  # 'ai' or 'calculation'
    
    # Core prediction data
    entry_level = Column(Float, nullable=False)   # Entry price
    stop_loss = Column(Float, nullable=False)     # SL price
    take_profit = Column(Float, nullable=False)   # TP price
    confidence = Column(Float, nullable=False)    # Confidence 0-100
    
    # Validation field (filled later)
    accuracy = Column(Float, nullable=True)       # Actual accuracy result (empty initially)
    
    # Optional metadata
    coin = Column(String(10), default='BTC')      # BTC or ETH
    notes = Column(String(500), nullable=True)    # Optional notes
    
    # Timestamps for tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)

class LearningInsight(Base):
    __tablename__ = 'learning_insights'
    
    id = Column(Integer, primary_key=True)
    insight_type = Column(String(50), nullable=False)  # weekly, monthly, best_setup, etc.
    period = Column(String(50))  # 2025-W20, 2025-05, etc.
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PredictionHistory(Base):
    __tablename__ = 'prediction_history'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    prediction_data = Column(JSON, nullable=False)
    accuracy_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.Session = None
        self.use_database = False
        self.initialize_database()
    
    def _migrate_sqlite_schema(self):
        """Migrate SQLite schema to add missing columns"""
        try:
            with self.engine.connect() as conn:
                # Get existing columns
                result = conn.execute(text("PRAGMA table_info(predictions)"))
                existing_columns = {row[1] for row in result.fetchall()}
                
                # Define required columns for new simplified schema
                required_columns = {
                    'time': 'VARCHAR(20)',
                    'method': 'VARCHAR(20) NOT NULL DEFAULT "ai"',
                    'entry_level': 'FLOAT',
                    'stop_loss': 'FLOAT', 
                    'take_profit': 'FLOAT',
                    'confidence': 'FLOAT',
                    'accuracy': 'FLOAT',
                    'coin': 'VARCHAR(10) DEFAULT "BTC"',
                    'notes': 'VARCHAR(500)',
                    'created_at': 'DATETIME',
                    'validated_at': 'DATETIME'
                }
                
                # Add missing columns
                added_columns = []
                for column_name, column_type in required_columns.items():
                    if column_name not in existing_columns:
                        try:
                            conn.execute(text(f"ALTER TABLE predictions ADD COLUMN {column_name} {column_type}"))
                            added_columns.append(column_name)
                            logger.info(f"Added SQLite column: {column_name}")
                        except Exception as e:
                            logger.warning(f"Failed to add SQLite column {column_name}: {e}")
                
                conn.commit()
                
                if added_columns:
                    logger.info(f"SQLite schema migration completed. Added columns: {added_columns}")
                else:
                    logger.info("SQLite schema is up to date")
                
                return True
                
        except Exception as e:
            logger.error(f"SQLite schema migration failed: {e}")
            return False
    
    def initialize_database(self):
        """Initialize database connection with enhanced PostgreSQL support for Render"""
        try:
            # Check for database URL (Render provides DATABASE_URL)
            database_url = os.getenv('DATABASE_URL')
            
            if database_url:
                # Fix for Render's PostgreSQL URL format
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
                logger.info("Connecting to PostgreSQL database...")
                # Enhanced PostgreSQL connection with proper settings for Render
                self.engine = create_engine(
                    database_url,
                    echo=False,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_recycle=300,    # Recycle connections every 5 minutes
                    connect_args={
                        "sslmode": "require",  # Require SSL for security
                    }
                )
                
            else:
                # Local development - use SQLite
                logger.info("Using local SQLite database...")
                self.engine = create_engine('sqlite:///crypto_predictions.db', echo=False)
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.use_database = True
            
            # For SQLite, check and migrate schema if needed
            if not database_url:  # SQLite (local)
                self._migrate_sqlite_schema()
            
            # Test connection
            session = self.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            
            logger.info("Database initialized successfully!")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.info("Falling back to JSON file storage...")
            self.use_database = False
    
    def get_session(self) -> Session:
        """Get database session"""
        if not self.use_database:
            raise Exception("Database not available")
        return self.Session()
    
    def save_prediction(self, prediction_data: Dict) -> bool:
        """Save prediction to database or JSON file"""
        if self.use_database:
            return self._save_prediction_db(prediction_data)
        else:
            return self._save_prediction_json(prediction_data, "detailed_predictions.json")
    
    def _save_prediction_db(self, prediction_data: Dict) -> bool:
        """Save prediction to database"""
        try:
            session = self.get_session()
            
            # Create prediction record with simplified structure
            record = PredictionRecord(
                date=prediction_data.get('date'),
                time=prediction_data.get('time'),
                timestamp=datetime.fromisoformat(prediction_data.get('timestamp').replace('Z', '+00:00')) if prediction_data.get('timestamp') else datetime.utcnow(),
                method=prediction_data.get('method'),
                entry_level=prediction_data.get('entry_level'),
                stop_loss=prediction_data.get('stop_loss'),
                take_profit=prediction_data.get('take_profit'),
                confidence=prediction_data.get('confidence'),
                accuracy=prediction_data.get('accuracy'),  # Initially None/empty
                coin=prediction_data.get('coin', 'BTC'),
                notes=prediction_data.get('notes'),
                validated_at=datetime.fromisoformat(prediction_data.get('validated_at').replace('Z', '+00:00')) if prediction_data.get('validated_at') else None
            )
            
            session.add(record)
            session.commit()
            session.close()
            logger.info("Prediction saved to database successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prediction to database: {e}")
            if 'session' in locals():
                session.rollback()
                session.close()
            return False
    
    def _save_prediction_json(self, prediction_data: Dict, filename: str) -> bool:
        """Save prediction to JSON file (fallback)"""
        try:
            # Load existing data
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
            else:
                data = []
            
            # Add new prediction
            data.append(prediction_data)
            
            # Save back to file
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4, default=str)
            
            logger.info(f"Prediction saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prediction to JSON: {e}")
            return False
    
    def load_predictions(self, limit: Optional[int] = None) -> List[Dict]:
        """Load predictions from database or JSON file"""
        if self.use_database:
            return self._load_predictions_db(limit)
        else:
            return self._load_predictions_json("detailed_predictions.json", limit)
    
    def _load_predictions_db(self, limit: Optional[int] = None) -> List[Dict]:
        """Load predictions from database"""
        try:
            session = self.get_session()
            query = session.query(PredictionRecord).order_by(PredictionRecord.timestamp.desc())
            
            if limit:
                query = query.limit(limit)
            
            records = query.all()
            
            predictions = []
            for record in records:
                prediction = {
                    'date': record.date,
                    'time': record.time,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'method': record.method,
                    'entry_level': record.entry_level,
                    'stop_loss': record.stop_loss,
                    'take_profit': record.take_profit,
                    'confidence': record.confidence,
                    'accuracy': record.accuracy,
                    'coin': record.coin,
                    'notes': record.notes,
                    'validated_at': record.validated_at.isoformat() if record.validated_at else None
                }
                predictions.append(prediction)
            
            session.close()
            return predictions
            
        except Exception as e:
            logger.error(f"Error loading predictions from database: {e}")
            session.close()
            return []
    
    def _load_predictions_json(self, filename: str, limit: Optional[int] = None) -> List[Dict]:
        """Load predictions from JSON file (fallback)"""
        try:
            if not os.path.exists(filename):
                return []
            
            with open(filename, 'r') as f:
                data = json.load(f)
            
            if limit:
                data = data[-limit:]
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading predictions from JSON: {e}")
            return []
    
    def update_prediction_validation(self, prediction_id: str, validation_points: List[Dict], accuracy: float = None) -> bool:
        """Update prediction validation data"""
        if self.use_database:
            return self._update_prediction_validation_db(prediction_id, validation_points, accuracy)
        else:
            return self._update_prediction_validation_json(prediction_id, validation_points, accuracy)
    
    def _update_prediction_validation_db(self, prediction_id: str, validation_points: List[Dict], accuracy: float = None) -> bool:
        """Update prediction validation in database"""
        try:
            session = self.get_session()
            
            # Find prediction by timestamp (using as ID for JSON compatibility)
            record = session.query(PredictionRecord).filter(
                PredictionRecord.timestamp == datetime.fromisoformat(prediction_id.replace('Z', '+00:00'))
            ).first()
            
            if record:
                record.validation_points = validation_points
                record.validated_at = datetime.utcnow()
                if accuracy is not None:
                    record.accuracy = accuracy
                
                session.commit()
                session.close()
                return True
            
            session.close()
            return False
            
        except Exception as e:
            logger.error(f"Error updating prediction validation in database: {e}")
            session.rollback()
            session.close()
            return False
    
    def _update_prediction_validation_json(self, prediction_id: str, validation_points: List[Dict], accuracy: float = None) -> bool:
        """Update prediction validation in JSON file"""
        try:
            filename = "detailed_predictions.json"
            if not os.path.exists(filename):
                return False
            
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Find and update prediction
            for prediction in data:
                if prediction.get('timestamp') == prediction_id:
                    prediction['validation_points'] = validation_points
                    prediction['validated_at'] = datetime.utcnow().isoformat()
                    if accuracy is not None:
                        prediction['accuracy'] = accuracy
                    break
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4, default=str)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating prediction validation in JSON: {e}")
            return False
    
    def save_learning_insight(self, insight_type: str, period: str, data: Dict) -> bool:
        """Save learning insight"""
        if self.use_database:
            return self._save_learning_insight_db(insight_type, period, data)
        else:
            return self._save_learning_insight_json(insight_type, period, data)
    
    def _save_learning_insight_db(self, insight_type: str, period: str, data: Dict) -> bool:
        """Save learning insight to database"""
        try:
            session = self.get_session()
            
            # Check if insight already exists
            existing = session.query(LearningInsight).filter(
                LearningInsight.insight_type == insight_type,
                LearningInsight.period == period
            ).first()
            
            if existing:
                existing.data = data
                existing.updated_at = datetime.utcnow()
            else:
                insight = LearningInsight(
                    insight_type=insight_type,
                    period=period,
                    data=data
                )
                session.add(insight)
            
            session.commit()
            session.close()
            return True
            
        except Exception as e:
            logger.error(f"Error saving learning insight to database: {e}")
            session.rollback()
            session.close()
            return False
    
    def _save_learning_insight_json(self, insight_type: str, period: str, data: Dict) -> bool:
        """Save learning insight to JSON file"""
        try:
            filename = "deep_learning_insights.json"
            
            # Load existing insights
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    insights = json.load(f)
            else:
                insights = {}
            
            # Update or add insight
            key = f"{insight_type}_{period}"
            insights[key] = {
                'insight_type': insight_type,
                'period': period,
                'data': data,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            with open(filename, 'w') as f:
                json.dump(insights, f, indent=4, default=str)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving learning insight to JSON: {e}")
            return False
    
    def get_learning_insights(self, insight_type: Optional[str] = None) -> List[Dict]:
        """Get learning insights"""
        if self.use_database:
            return self._get_learning_insights_db(insight_type)
        else:
            return self._get_learning_insights_json(insight_type)
    
    def _get_learning_insights_db(self, insight_type: Optional[str] = None) -> List[Dict]:
        """Get learning insights from database"""
        try:
            session = self.get_session()
            query = session.query(LearningInsight)
            
            if insight_type:
                query = query.filter(LearningInsight.insight_type == insight_type)
            
            records = query.order_by(LearningInsight.updated_at.desc()).all()
            
            insights = []
            for record in records:
                insight = {
                    'insight_type': record.insight_type,
                    'period': record.period,
                    'data': record.data,
                    'updated_at': record.updated_at.isoformat() if record.updated_at else None
                }
                insights.append(insight)
            
            session.close()
            return insights
            
        except Exception as e:
            logger.error(f"Error getting learning insights from database: {e}")
            session.close()
            return []
    
    def _get_learning_insights_json(self, insight_type: Optional[str] = None) -> List[Dict]:
        """Get learning insights from JSON file"""
        try:
            filename = "deep_learning_insights.json"
            if not os.path.exists(filename):
                return []
            
            with open(filename, 'r') as f:
                insights = json.load(f)
            
            result = []
            for key, insight in insights.items():
                if not insight_type or insight.get('insight_type') == insight_type:
                    result.append(insight)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting learning insights from JSON: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check database health and return status"""
        status = {
            'database_available': self.use_database,
            'connection_type': 'database' if self.use_database else 'json_files',
            'engine_url': str(self.engine.url) if self.engine else None,
            'tables_exist': False,
            'total_predictions': 0,
            'total_insights': 0
        }
        
        if self.use_database:
            try:
                from sqlalchemy import inspect
                session = self.get_session()
                
                # Check if tables exist using modern SQLAlchemy inspector
                inspector = inspect(self.engine)
                status['tables_exist'] = inspector.has_table('predictions')
                
                # Count records
                if status['tables_exist']:
                    status['total_predictions'] = session.query(PredictionRecord).count()
                    status['total_insights'] = session.query(LearningInsight).count()
                
                session.close()
                
            except Exception as e:
                status['error'] = str(e)
        
        else:
            # Check JSON files
            if os.path.exists('detailed_predictions.json'):
                try:
                    with open('detailed_predictions.json', 'r') as f:
                        data = json.load(f)
                        status['total_predictions'] = len(data)
                except:
                    pass
            
            if os.path.exists('deep_learning_insights.json'):
                try:
                    with open('deep_learning_insights.json', 'r') as f:
                        data = json.load(f)
                        status['total_insights'] = len(data)
                except:
                    pass
        
        return status
    
    def save_simple_prediction(self, date: str, time: str, method: str, entry_level: float, 
                              stop_loss: float, take_profit: float, confidence: float, 
                              coin: str = 'BTC', notes: str = None) -> bool:
        """Save a simple prediction record with core data only"""
        prediction_data = {
            'date': date,
            'time': time,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'method': method,
            'entry_level': entry_level,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': confidence,
            'accuracy': None,  # Empty field for later validation
            'coin': coin,
            'notes': notes
        }
        return self.save_prediction(prediction_data)
    
    def update_prediction_accuracy(self, prediction_id: int, accuracy: float) -> bool:
        """Update the accuracy field for a specific prediction"""
        if self.use_database:
            try:
                session = self.get_session()
                record = session.query(PredictionRecord).filter(PredictionRecord.id == prediction_id).first()
                
                if record:
                    record.accuracy = accuracy
                    record.validated_at = datetime.utcnow()
                    session.commit()
                    session.close()
                    logger.info(f"Updated accuracy for prediction {prediction_id}: {accuracy}")
                    return True
                else:
                    logger.warning(f"Prediction {prediction_id} not found")
                    session.close()
                    return False
                    
            except Exception as e:
                logger.error(f"Error updating prediction accuracy: {e}")
                if 'session' in locals():
                    session.rollback()
                    session.close()
                return False
        else:
            logger.warning("Database not available for accuracy update")
            return False
    
    def get_predictions_by_method(self, method: str, limit: int = 50) -> List[Dict]:
        """Get predictions filtered by method (ai or calculation)"""
        if self.use_database:
            try:
                session = self.get_session()
                query = session.query(PredictionRecord).filter(
                    PredictionRecord.method == method
                ).order_by(PredictionRecord.timestamp.desc()).limit(limit)
                
                records = query.all()
                predictions = []
                
                for record in records:
                    prediction = {
                        'id': record.id,
                        'date': record.date,
                        'time': record.time,
                        'method': record.method,
                        'entry_level': record.entry_level,
                        'stop_loss': record.stop_loss,
                        'take_profit': record.take_profit,
                        'confidence': record.confidence,
                        'accuracy': record.accuracy,
                        'coin': record.coin,
                        'notes': record.notes,
                        'validated_at': record.validated_at.isoformat() if record.validated_at else None
                    }
                    predictions.append(prediction)
                
                session.close()
                return predictions
                
            except Exception as e:
                logger.error(f"Error getting predictions by method: {e}")
                if 'session' in locals():
                    session.close()
                return []
        else:
            return []

# Global database manager instance
db_manager = DatabaseManager() 