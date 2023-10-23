from pathlib import Path


PROJECT_DIR = Path(__file__).parent
CHATBOT_SECRETS = Path(f'{PROJECT_DIR}/chatbot_secrets')
TABLE_DESCRIPTIONS = Path(f'{CHATBOT_SECRETS}/table_descriptions')
ALLOWED_USERS = Path(f'{CHATBOT_SECRETS}/allowed_users.txt')
OPENAI_KEY = Path(f'{CHATBOT_SECRETS}/api_key.key')
BOT_KEY = Path(f'{CHATBOT_SECRETS}/tg_key.key')
SQL_CONTEXT = Path(f'{CHATBOT_SECRETS}/context.txt')
CONTEXTS_DUMPS = Path(f'{CHATBOT_SECRETS}/contexts.pickle')
HISTORY = Path(f'{CHATBOT_SECRETS}/history.log')
