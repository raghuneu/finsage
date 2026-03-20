import sys
from snowflake_connection import get_session


session = get_session()




session.close()