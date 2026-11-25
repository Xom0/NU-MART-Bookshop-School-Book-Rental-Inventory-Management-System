from dataclasses import dataclass
@dataclass
class Book:
    book_id: str
    title: str
    subject: str
    edition: int
    condition: str
    availability: str = 'Available'
