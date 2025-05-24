import os
import json
import logging
from datetime import datetime
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
    date = Column(String(20), nullable=False)
    session = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Market data
    btc_price = Column(Float)
    eth_price = Column(Float)
    btc_rsi = Column(Float)
    eth_rsi = Column(Float)
    fear_greed = Column(Integer)
    
    # Predictions (stored as JSON)
    predictions_data = Column(JSON, nullable=False)
    
    # Validation data
    validation_points = Column(JSON, default=list)
    final_accuracy = Column(Float)
    
    # Processing flags
    ml_processed = Column(Boolean, default=False)
    hourly_validated = Column(Boolean, default=False)
    last_validation = Column(DateTime)
    
    # Enhanced fields for validation learning
    trade_metrics = Column(JSON)
    risk_analysis = Column(JSON)

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
        self.SessionLocal = None
        self.use_database = False
        self.initialize_database()
    
    def initialize_database(self):
        """Initialize database connection or fallback to JSON files"""
        try:
            # Check for database URL (Render provides DATABASE_URL)
            database_url = os.getenv('DATABASE_URL')
            
            if database_url:
                # Fix for Render's PostgreSQL URL format
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
                logger.info("Connecting to PostgreSQL database...")
                self.engine = create_engine(database_url, echo=False)
                
            else:
                # Local development - use SQLite
                logger.info("Using local SQLite database...")
                self.engine = create_engine('sqlite:///crypto_predictions.db', echo=False)
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.use_database = True
            logger.info("Database initialized successfully!")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.info("Falling back to JSON file storage...")
            self.use_database = False
    
    def get_session(self) -> Session:
        """Get database session"""
        if not self.use_database:
            raise Exception("Database not available")
        return self.SessionLocal()
    
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
            
            # Extract market data
            market_data = prediction_data.get('market_data', {})
            
            # Create prediction record
            record = PredictionRecord(
                date=prediction_data.get('date'),
                session=prediction_data.get('session'),
                timestamp=datetime.fromisoformat(prediction_data.get('timestamp').replace('Z', '+00:00')) if prediction_data.get('timestamp') else datetime.utcnow(),
                btc_price=market_data.get('btc_price'),
                eth_price=market_data.get('eth_price'),
                btc_rsi=market_data.get('btc_rsi'),
                eth_rsi=market_data.get('eth_rsi'),
                fear_greed=market_data.get('fear_greed'),
                predictions_data=prediction_data.get('predictions', {}),
                validation_points=prediction_data.get('validation_points', []),
                final_accuracy=prediction_data.get('final_accuracy'),
                ml_processed=prediction_data.get('ml_processed', False),
                hourly_validated=prediction_data.get('hourly_validated', False),
                last_validation=datetime.fromisoformat(prediction_data.get('last_validation').replace('Z', '+00:00')) if prediction_data.get('last_validation') else None,
                trade_metrics=prediction_data.get('trade_metrics'),
                risk_analysis=prediction_data.get('risk_analysis')
            )
            
            session.add(record)
            session.commit()
            session.close()
            logger.info("Prediction saved to database successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prediction to database: {e}")
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
                    'session': record.session,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'market_data': {
                        'btc_price': record.btc_price,
                        'eth_price': record.eth_price,
                        'btc_rsi': record.btc_rsi,
                        'eth_rsi': record.eth_rsi,
                        'fear_greed': record.fear_greed
                    },
                    'predictions': record.predictions_data,
                    'validation_points': record.validation_points,
                    'final_accuracy': record.final_accuracy,
                    'ml_processed': record.ml_processed,
                    'hourly_validated': record.hourly_validated,
                    'last_validation': record.last_validation.isoformat() if record.last_validation else None,
                    'trade_metrics': record.trade_metrics,
                    'risk_analysis': record.risk_analysis
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
                record.hourly_validated = True
                record.last_validation = datetime.utcnow()
                if accuracy is not None:
                    record.final_accuracy = accuracy
                
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
                    prediction['hourly_validated'] = True
                    prediction['last_validation'] = datetime.utcnow().isoformat()
                    if accuracy is not None:
                        prediction['final_accuracy'] = accuracy
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

# Global database manager instance
db_manager = DatabaseManager() 