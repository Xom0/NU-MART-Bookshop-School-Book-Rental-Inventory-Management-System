from dataclasses import dataclass
@dataclass
class Rental:
    rental_id: int
    student_id: str
    book_id: str
    rental_date: str
    due_date: str
    return_date: str | None
    status: str
