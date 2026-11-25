from helpers.database import Database
from managers.student_manager import StudentManager
import pytest

def test_student_search_and_enrolment(client):
    with client.application.app_context():
        conn=Database.connect(client.application.config['DATABASE'])
        try:
            result=StudentManager.search_student(conn,'Marcus')
            assert result[0]['student_id']=='ST002'
            assert StudentManager.verify_student(conn,'ST002')['grade']==10
            with pytest.raises(ValueError,match='not currently enrolled'):
                StudentManager.verify_student(conn,'ST004')
        finally: conn.close()
