class EventStatus:
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class EventProducer:
    CONSTRUCTION_API = "construction-api"