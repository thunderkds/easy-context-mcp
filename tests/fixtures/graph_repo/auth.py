"""Password checks."""


def verify_password(user, password):
    return user["password"] == password
