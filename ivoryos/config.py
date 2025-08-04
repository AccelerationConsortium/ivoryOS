import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', None)

    OUTPUT_FOLDER = os.path.join(os.path.abspath(os.curdir), 'ivoryos_data')
    CSV_FOLDER = os.path.join(OUTPUT_FOLDER, 'config_csv/')
    SCRIPT_FOLDER = os.path.join(OUTPUT_FOLDER, 'scripts/')
    DATA_FOLDER = os.path.join(OUTPUT_FOLDER, 'results/')
    DUMMY_DECK = os.path.join(OUTPUT_FOLDER, 'pseudo_deck/')
    LLM_OUTPUT = os.path.join(OUTPUT_FOLDER, 'llm_output/')
    DECK_HISTORY = os.path.join(OUTPUT_FOLDER, 'deck_history.txt')
    LOGGERS_PATH = "default.log"

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(OUTPUT_FOLDER, 'ivoryos.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ENABLE_LLM = True if OPENAI_API_KEY else False
    OFF_LINE = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Use an in-memory SQLite database for tests
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing forms



class DemoConfig(Config):
    DEBUG = False
    DEMO_MODE = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    OUTPUT_FOLDER = os.path.join(os.path.abspath(os.curdir), '/tmp/ivoryos_data')
    CSV_FOLDER = os.path.join(OUTPUT_FOLDER, 'config_csv/')
    SCRIPT_FOLDER = os.path.join(OUTPUT_FOLDER, 'scripts/')
    DATA_FOLDER = os.path.join(OUTPUT_FOLDER, 'results/')
    DUMMY_DECK = os.path.join(OUTPUT_FOLDER, 'pseudo_deck/')
    LLM_OUTPUT = os.path.join(OUTPUT_FOLDER, 'llm_output/')
    DECK_HISTORY = os.path.join(OUTPUT_FOLDER, 'deck_history.txt')
    # session and cookies
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_HTTPONLY = True

def get_config(env='dev'):
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    elif env == 'demo':
        return DemoConfig()
    return DevelopmentConfig()
