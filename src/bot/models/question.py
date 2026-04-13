from dataclasses import dataclass


@dataclass
class LiteMarket:
    id: str
    question: str
    url: str
    probability: float
    volume: float
    close_time: int
    is_resolved: bool
    resolution: str | None
    resolution_time: int | None
    group_slugs: list[str]

    @classmethod
    def from_api(cls, data: dict) -> "LiteMarket":
        return cls(
            id=data["id"],
            question=data.get("question", ""),
            url=data.get("url", ""),
            probability=data.get("probability", 0.5),
            volume=data.get("volume", 0),
            close_time=data.get("closeTime", 0),
            is_resolved=data.get("isResolved", False),
            resolution=data.get("resolution"),
            resolution_time=data.get("resolutionTime"),
            group_slugs=data.get("groupSlugs", []),
        )
