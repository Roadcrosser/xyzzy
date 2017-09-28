class Game:
    def __init__(self, name, data):
        self.name = name
        self.path = data["path"]
        self.url = data.get("url")
        self.aliases = data.get("aliases", [])
        self.author = data.get("author")