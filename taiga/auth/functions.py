import re

def user_is_itaipuparquetec(username:str):
    regex_pattern_itaipuparquetec = r'^[a-zA-Z]+\.[a-zA-Z]+(\@itaipuparquetec\.org\.br)?$|^[a-zA-Z]+(\@itaipuparquetec\.org\.br)?$'
    if not re.match(regex_pattern_itaipuparquetec, username):
        return False
    return True  