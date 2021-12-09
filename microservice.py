class Microservice:
    ip = None
    dependency_info = []
    name = None
    creator = None
    tile = None

    dependencies = None
    max_age = None

    def __init__(self, host, d, name=None, creator=None, tile=None):
        self.ip = host
        self.dependency_info = d
        self.name = name
        self.creator = creator
        self.tile = tile

    def __hash__(self) -> int:
        return hash(self.ip)

    def __eq__(self, other) -> bool:
        return self.ip == other.ip

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return f'Microservice(ip={self.ip},  name={self.name}, creator={self.creator})'