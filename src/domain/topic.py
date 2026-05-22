from dataclasses import dataclass


@dataclass
class Topic:
    name: str
    description: str

    @property
    def playlist_name(self) -> str:
        return f"WL/{self.name}"
