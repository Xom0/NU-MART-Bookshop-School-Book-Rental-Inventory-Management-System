import pytest
from managers.receipt_manager import ReceiptManager

@pytest.mark.parametrize('grade,edition',[(9,1),(10,2),(11,2),(12,3),(13,3)])
def test_grade_to_edition_mapping(grade,edition):
    assert ReceiptManager.get_edition(grade)==edition

def test_invalid_grade():
    with pytest.raises(ValueError): ReceiptManager.get_edition(8)
