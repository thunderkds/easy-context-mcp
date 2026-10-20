# ruff: noqa
import auth
from auth import authenticate
from stock import Inventory
import m1, m2, m3, m4


class Base:
    pass


class Service(Base):
    def start(self):
        self.stop()
        return helper()

    def stop(self):
        return 0


def helper():
    return 1


def run(user):
    helper()
    dup()
    shared_util()
    normalize(user)
    run(user)
    print(user)
    out = []
    out.append(user)
    auth.check(user)
    Inventory.add(user)
    return authenticate(user)
