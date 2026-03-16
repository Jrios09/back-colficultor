import bcrypt

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    password_byte_enc = plain.encode('utf-8')
    hashed_password_byte_enc = hashed.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)