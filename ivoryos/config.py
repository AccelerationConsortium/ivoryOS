import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', None)

    OUTPUT_FOLDER = os.path.join(os.path.abspath(os.curdir), 'ivoryos_data')
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
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


def get_config(env='dev'):
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    return DevelopmentConfig()
