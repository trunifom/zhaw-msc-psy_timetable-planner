"""
ZHAW MSc Psychology - Timetable Planner (Data Integration Layer)
Author: HealthData CodeArchitect
Description: Robust data ingestion, validation, and transformation module.
Focuses on defensive programming to ensure high UI/UX stability by catching
and correcting data anomalies before they reach the presentation layer.
"""

import pandas as pd
import logging
from typing import List, Dict, Any
from pydantic import ValidationError

# Assuming ZHAWModule is a Pydantic BaseModel defined in models.py
from models import ZHAWModule

# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================
# Set up a module-specific logger for backend debugging without cluttering the UI
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ==========================================
# 2. CUSTOM EXCEPTIONS
# ==========================================
class DataLoaderError(Exception):
    """Base exception for data loading issues. Designed to be caught by the GUI."""
    pass

class MissingColumnError(DataLoaderError):
    """Raised when critical columns are missing from the uploaded dataset."""
    pass

class DataSanitizationError(DataLoaderError):
    """Raised when the data cannot be coerced into the required formats."""
    pass

# ==========================================
# 3. CONSTANTS & MAPPINGS
# ==========================================
# Define the critical columns required for the application to function.
# This serves as our schema contract.
REQUIRED_COLUMNS = {
    "wochentag", 
    "startzeit", 
    "endzeit", 
    "modulname", 
    "ects"
}

# Optional columns that enhance the UI but aren't strictly necessary for the algorithm
OPTIONAL_COLUMNS = {
    "modultyp", 
    "dozierende", 
    "raum"
}

# ==========================================
# 4. HELPER FUNCTIONS (DATA TRANSFORMATIONS)
# ==========================================
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitizes DataFrame columns to prevent KeyError caused by minor typos,
    varying capitalizations, or trailing whitespaces in user uploads.
    
    Args:
        df (pd.DataFrame): The raw uploaded pandas DataFrame.
        
    Returns:
        pd.DataFrame: DataFrame with normalized column names.
    """
    logger.info("Normalizing dataframe column names...")
    # Strip whitespace, convert to lowercase, and replace spaces with underscores
    df.columns = df.columns.str.strip().str.lower().str.replace(r'\s+', '_', regex=True)
    return df

def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and prepares data types before Pydantic validation.
    Handles NaN values which frequently crash strict type validators.
    
    Args:
        df (pd.DataFrame): The normalized pandas DataFrame.
        
    Returns:
        pd.DataFrame: Sanitized DataFrame ready for object mapping.
    """
    logger.info("Sanitizing data types and handling missing values...")
    
    try:
        # Fill missing string columns with empty strings or default placeholders
        string_cols = ["modulname", "wochentag", "modultyp", "dozierende", "raum"]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].fillna("N/A").astype(str)
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

        # Ensure ECTS is numeric, coercion forces invalid parsing to NaN, then fill with 0
        if "ects" in df.columns:
            df["ects"] = pd.to_numeric(df["ects"], errors="coerce").fillna(0).astype(int)

        # Standardize time strings (ensures format like "HH:MM")
        # Removing any random whitespace that might break datetime parsing
        time_cols = ["startzeit", "endzeit"]
        for col in time_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        return df

    except Exception as e:
        logger.error(f"Sanitization failed: {str(e)}")
        raise DataSanitizationError(f"Failed to clean dataset: {str(e)}")

# ==========================================
# 5. MAIN DATA LOADER LOGIC
# ==========================================
def load_schedule_from_dataframe(raw_df: pd.DataFrame) -> List[ZHAWModule]:
    """
    Main entry point for data ingestion. Takes a raw Pandas DataFrame (uploaded via UI),
    validates its structure, sanitizes the contents, and maps it to strongly-typed 
    Pydantic models (ZHAWModule).

    Args:
        raw_df (pd.DataFrame): The raw dataframe from st.file_uploader.

    Returns:
        List[ZHAWModule]: A list of validated module objects.

    Raises:
        MissingColumnError: If essential scheduling columns are absent.
        DataLoaderError: For general Pydantic validation failures.
    """
    if raw_df is None or raw_df.empty:
        logger.warning("Received empty DataFrame.")
        return []

    # 1. Create an isolated copy to prevent SettingWithCopyWarnings
    df = raw_df.copy()

    # 2. Normalize columns (e.g., " Startzeit " -> "startzeit")
    df = _normalize_columns(df)

    # 3. Structural Validation
    current_cols = set(df.columns)
    missing_cols = REQUIRED_COLUMNS - current_cols
    if missing_cols:
        error_msg = f"Invalid dataset format. Missing critical columns: {', '.join(missing_cols)}"
        logger.error(error_msg)
        # Raising a custom error allows the GUI to catch it and display a friendly st.error()
        raise MissingColumnError(error_msg)

    # 4. Data Sanitization (Handle NaNs, cast types securely)
    df = _sanitize_dataframe(df)

    # 5. Object Mapping (DataFrame -> List[Pydantic Models])
    processed_modules: List[ZHAWModule] = []
    validation_errors = 0

    logger.info(f"Attempting to parse {len(df)} rows into ZHAWModule objects.")
    
    for index, row in df.iterrows():
        try:
            # Convert pandas Series to dictionary, filtering out unexpected columns dynamically
            row_dict: Dict[str, Any] = row.to_dict()
            
            # Instantiate Pydantic model (which handles internal datetime parsing and strict validation)
            module_obj = ZHAWModule(**row_dict)
            processed_modules.append(module_obj)
            
        except ValidationError as ve:
            # Catch row-level validation errors (e.g., impossible time format)
            validation_errors += 1
            logger.warning(f"Row {index + 1} failed validation: {ve}. Skipping row.")
            # In a strict environment, we might raise here. For UI/UX, we skip bad rows
            # but log them so the user isn't completely blocked by one bad cell.
        except Exception as e:
            validation_errors += 1
            logger.error(f"Unexpected error parsing row {index + 1}: {e}")

    # Summary logging
    logger.info(f"Successfully loaded {len(processed_modules)} modules. Failed rows: {validation_errors}")
    
    if len(processed_modules) == 0 and len(df) > 0:
        # If all rows failed validation, throw an error to the UI
        raise DataLoaderError("All rows failed data validation. Please check your time formats (HH:MM) and data types.")

    return processed_modules