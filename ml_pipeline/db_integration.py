"""
Database Integration — ML System Database Schema & Operations
==============================================================
Extends the existing smartybee_db with ML-specific tables for:
- Predictions logging
- Score storage
- Error feedback
- Model version tracking
- Writer identification (for holdout strategy)
"""

import json
import time
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection
from ml_pipeline.ml_config import CLASS_TO_LETTER, FOLDER_TO_LETTER, FOLDER_TO_CLASS


# ============================================================
# SCHEMA CREATION
# ============================================================

ML_SCHEMA_SQL = """
-- ============================================================
-- ML PIPELINE DATABASE TABLES
-- ============================================================

-- Model version tracking
CREATE TABLE IF NOT EXISTS ML_Model_Version (
    VersionID INT AUTO_INCREMENT PRIMARY KEY,
    VersionTag VARCHAR(50) NOT NULL,
    ModelPath VARCHAR(500),
    TrainAccuracy DECIMAL(5,2),
    ValidAccuracy DECIMAL(5,2),
    TestAccuracy DECIMAL(5,2),
    NumClasses INT DEFAULT 14,
    NumEpochs INT,
    BestEpoch INT,
    TrainingConfig JSON,
    ClassAccuracies JSON,
    ConfusionMatrix JSON,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    IsActive BOOLEAN DEFAULT FALSE
);

-- Prediction log (every recognition attempt)
CREATE TABLE IF NOT EXISTS ML_Prediction (
    PredictionID INT AUTO_INCREMENT PRIMARY KEY,
    ChildID INT NULL,
    LetterID INT NULL,
    TargetFolderID INT NULL,
    TargetLetter VARCHAR(10) CHARACTER SET utf8mb4 NULL,
    PredictedClassIndex INT,
    PredictedFolderID INT,
    PredictedLetter VARCHAR(10) CHARACTER SET utf8mb4,
    Confidence DECIMAL(5,4),
    TargetConfidence DECIMAL(5,4) NULL,
    IsMatch BOOLEAN,
    GatekeeperAllowed BOOLEAN,
    GatekeeperReason TEXT,
    AllProbabilities JSON,
    NumStrokePoints INT,
    ModelVersionID INT NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE SET NULL,
    FOREIGN KEY (ModelVersionID) REFERENCES ML_Model_Version(VersionID) ON DELETE SET NULL
);

-- Detailed scoring results (only for allowed attempts)
CREATE TABLE IF NOT EXISTS ML_Score (
    ScoreID INT AUTO_INCREMENT PRIMARY KEY,
    PredictionID INT,
    ChildID INT NULL,
    LetterID INT NULL,
    TemplateScore DECIMAL(5,2),
    StructuralScore DECIMAL(5,2) NULL,
    HybridScore DECIMAL(5,2) NULL,
    StarsEarned INT DEFAULT 0,
    ScoringMethod VARCHAR(20) DEFAULT 'template',
    Coverage DECIMAL(5,4) NULL,
    Excess DECIMAL(5,4) NULL,
    StructuralOverlap DECIMAL(5,4) NULL,
    BreakdownJSON JSON,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (PredictionID) REFERENCES ML_Prediction(PredictionID) ON DELETE CASCADE,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE SET NULL
);

-- Error feedback (human-readable)
CREATE TABLE IF NOT EXISTS ML_Error_Feedback (
    FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
    ScoreID INT NULL,
    PredictionID INT NULL,
    ChildID INT NULL,
    FeedbackLevel VARCHAR(20),
    Message TEXT,
    Suggestions JSON,
    ErrorAreas JSON,
    ErrorTypes JSON,
    ErrorIndices JSON,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ScoreID) REFERENCES ML_Score(ScoreID) ON DELETE CASCADE,
    FOREIGN KEY (PredictionID) REFERENCES ML_Prediction(PredictionID) ON DELETE CASCADE,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE SET NULL
);

-- Stroke data storage (raw for retraining)
CREATE TABLE IF NOT EXISTS ML_Stroke_Data (
    StrokeID INT AUTO_INCREMENT PRIMARY KEY,
    ChildID INT NULL,
    LetterID INT NULL,
    StrokeJSON JSON,
    NumPoints INT,
    ImagePath VARCHAR(500) NULL,
    PredictionID INT NULL,
    Score DECIMAL(5,2) NULL,
    IsVerified BOOLEAN DEFAULT FALSE,
    WriterTag VARCHAR(50) NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE SET NULL,
    FOREIGN KEY (PredictionID) REFERENCES ML_Prediction(PredictionID) ON DELETE SET NULL
);

-- Error log (system-level ML errors)
CREATE TABLE IF NOT EXISTS ML_Error_Log (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    Component VARCHAR(50),
    ErrorType VARCHAR(100),
    Message TEXT,
    StackTrace TEXT NULL,
    InputData JSON NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Training metadata and runs
CREATE TABLE IF NOT EXISTS ML_Training_Run (
    RunID INT AUTO_INCREMENT PRIMARY KEY,
    ModelVersionID INT NULL,
    StartedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    CompletedAt DATETIME NULL,
    Status ENUM('running', 'completed', 'failed', 'cancelled') DEFAULT 'running',
    NumTrainSamples INT,
    NumValidSamples INT,
    NumTestSamples INT,
    FinalTrainAcc DECIMAL(5,2) NULL,
    FinalValidAcc DECIMAL(5,2) NULL,
    FinalTestAcc DECIMAL(5,2) NULL,
    BestEpoch INT NULL,
    TotalEpochs INT NULL,
    Config JSON,
    HistoryJSON JSON NULL,
    FOREIGN KEY (ModelVersionID) REFERENCES ML_Model_Version(VersionID) ON DELETE SET NULL
);
"""


def create_ml_tables():
    """Create all ML-specific database tables."""
    conn = get_db_connection()
    if not conn:
        print("[ML DB] Failed to connect to database")
        return False

    try:
        cursor = conn.cursor()
        # Execute each statement separately
        for statement in ML_SCHEMA_SQL.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                cursor.execute(statement)
        conn.commit()
        print("[ML DB] All ML tables created successfully")
        return True
    except Exception as e:
        print(f"[ML DB] Error creating tables: {e}")
        return False
    finally:
        conn.close()


# ============================================================
# PREDICTION LOGGING
# ============================================================

def log_prediction(child_id, letter_id, target_letter, prediction_result, gatekeeper_result, model_version_id=None):
    """
    Log a prediction attempt to the database.
    
    Args:
        child_id: Child profile ID (from session)
        letter_id: Database letter ID
        target_letter: Expected Sinhala character
        prediction_result: dict from MLPredictor.predict()
        gatekeeper_result: dict from LetterRecognizer.validate_letter()
        model_version_id: Active model version ID
    
    Returns:
        prediction_id: int (for linking to scores)
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ML_Prediction 
            (ChildID, LetterID, TargetLetter, PredictedClassIndex, PredictedFolderID,
             PredictedLetter, Confidence, TargetConfidence, IsMatch, GatekeeperAllowed,
             GatekeeperReason, AllProbabilities, NumStrokePoints, ModelVersionID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            child_id,
            letter_id,
            target_letter,
            prediction_result.get('class_index'),
            prediction_result.get('class_id'),
            prediction_result.get('letter'),
            prediction_result.get('confidence', 0),
            gatekeeper_result.get('target_confidence', 0),
            gatekeeper_result.get('match', False),
            gatekeeper_result.get('allowed', True),
            gatekeeper_result.get('reason', ''),
            json.dumps(prediction_result.get('probabilities', {})),
            0,  # num_stroke_points will be updated
            model_version_id,
        ))
        prediction_id = cursor.lastrowid
        conn.commit()
        return prediction_id
    except Exception as e:
        print(f"[ML DB] Error logging prediction: {e}")
        return None
    finally:
        conn.close()


def log_score(prediction_id, child_id, letter_id, score_data, scoring_method='template'):
    """Log scoring results to the database."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ML_Score
            (PredictionID, ChildID, LetterID, TemplateScore, StructuralScore,
             HybridScore, StarsEarned, ScoringMethod, Coverage, Excess,
             StructuralOverlap, BreakdownJSON)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prediction_id,
            child_id,
            letter_id,
            score_data.get('score', 0),
            score_data.get('structural_score'),
            score_data.get('hybrid_score'),
            score_data.get('stars', 0),
            scoring_method,
            score_data.get('coverage'),
            score_data.get('excess'),
            score_data.get('structural_overlap'),
            json.dumps(score_data.get('breakdown', {})),
        ))
        score_id = cursor.lastrowid
        conn.commit()
        return score_id
    except Exception as e:
        print(f"[ML DB] Error logging score: {e}")
        return None
    finally:
        conn.close()


def log_error_feedback(score_id, prediction_id, child_id, feedback_data, error_data=None):
    """Log error feedback to the database."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ML_Error_Feedback
            (ScoreID, PredictionID, ChildID, FeedbackLevel, Message,
             Suggestions, ErrorAreas, ErrorTypes, ErrorIndices)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            score_id,
            prediction_id,
            child_id,
            feedback_data.get('level', ''),
            feedback_data.get('message', ''),
            json.dumps(feedback_data.get('suggestions', [])),
            json.dumps(feedback_data.get('error_areas', [])),
            json.dumps(error_data.get('error_types', {})) if error_data else None,
            json.dumps(error_data.get('error_indices', [])) if error_data else None,
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[ML DB] Error logging feedback: {e}")
        return None
    finally:
        conn.close()


def log_stroke_data(child_id, letter_id, stroke_points, prediction_id=None, score=None, image_path=None):
    """Store raw stroke data for future retraining."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        # Tag writer by child_id for holdout strategy
        writer_tag = f"child_{child_id}" if child_id else f"anon_{int(time.time())}"

        cursor.execute("""
            INSERT INTO ML_Stroke_Data
            (ChildID, LetterID, StrokeJSON, NumPoints, ImagePath,
             PredictionID, Score, WriterTag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            child_id,
            letter_id,
            json.dumps(stroke_points),
            len(stroke_points),
            image_path,
            prediction_id,
            score,
            writer_tag,
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[ML DB] Error logging stroke data: {e}")
        return None
    finally:
        conn.close()


def log_ml_error(component, error_type, message, stack_trace=None, input_data=None):
    """Log ML system errors."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ML_Error_Log (Component, ErrorType, Message, StackTrace, InputData)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            component,
            error_type,
            message,
            stack_trace,
            json.dumps(input_data) if input_data else None,
        ))
        conn.commit()
    except Exception as e:
        print(f"[ML DB] Error logging ML error: {e}")
    finally:
        conn.close()


def save_model_version(version_tag, model_path, training_log):
    """Save a trained model version to the database."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Deactivate all previous versions
        cursor.execute("UPDATE ML_Model_Version SET IsActive = FALSE")

        cursor.execute("""
            INSERT INTO ML_Model_Version
            (VersionTag, ModelPath, TrainAccuracy, ValidAccuracy, TestAccuracy,
             NumClasses, NumEpochs, BestEpoch, TrainingConfig, ClassAccuracies,
             ConfusionMatrix, IsActive)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """, (
            version_tag,
            model_path,
            training_log.get('history', {}).get('train_acc', [0])[-1] if training_log.get('history') else 0,
            training_log.get('best_val_acc', 0),
            training_log.get('test_acc', 0),
            training_log.get('config', {}).get('num_classes', 14),
            training_log.get('config', {}).get('epochs', 0),
            training_log.get('best_epoch', 0),
            json.dumps(training_log.get('config', {})),
            json.dumps(training_log.get('class_accuracies', {}), ensure_ascii=False),
            json.dumps(training_log.get('confusion_matrix', [])),
        ))
        version_id = cursor.lastrowid
        conn.commit()
        print(f"[ML DB] Saved model version {version_tag} (ID: {version_id})")
        return version_id
    except Exception as e:
        print(f"[ML DB] Error saving model version: {e}")
        return None
    finally:
        conn.close()


def get_active_model_version():
    """Get the currently active model version."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM ML_Model_Version WHERE IsActive = TRUE LIMIT 1")
        return cursor.fetchone()
    except Exception as e:
        print(f"[ML DB] Error fetching active model: {e}")
        return None
    finally:
        conn.close()


def get_writer_ids_for_holdout():
    """
    Get list of unique writer tags from collected stroke data.
    Used for writer-holdout cross-validation in retraining.
    
    Returns:
        list of writer_tag strings
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT WriterTag FROM ML_Stroke_Data WHERE WriterTag IS NOT NULL")
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[ML DB] Error fetching writer IDs: {e}")
        return []
    finally:
        conn.close()


if __name__ == "__main__":
    print("Creating ML database tables...")
    success = create_ml_tables()
    if success:
        print("Done! All ML tables created.")
    else:
        print("Failed to create some tables. Check database connection.")
