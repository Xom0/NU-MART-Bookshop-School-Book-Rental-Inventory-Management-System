from dataclasses import dataclass
@dataclass
class Reminder:
    reminder_id: int
    rental_id: int
    message: str
    created_at: str
    status: str
