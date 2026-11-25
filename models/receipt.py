from dataclasses import dataclass
@dataclass
class Receipt:
    receipt_id: int
    student_id: str
    issued_at: str
