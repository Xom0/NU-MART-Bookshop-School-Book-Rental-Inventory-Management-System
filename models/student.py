from dataclasses import dataclass
@dataclass
class Student:
    student_id: str
    first_name: str
    last_name: str
    grade: int
    class_name: str
    enrolment_status: str
