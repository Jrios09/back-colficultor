users = []

def register(user):

    for u in users:
        if u["email"] == user.email:
            return {"error": "El correo ya existe"}

    users.append(user.dict())

    return {"message": "Usuario registrado correctamente"}


def login(user):

    for u in users:
        if u["email"] == user.email and u["password"] == user.password:
            return {"message": "Login exitoso"}

    return {"error": "Credenciales incorrectas"}


def logout():
    return {"message": "Logout exitoso"}