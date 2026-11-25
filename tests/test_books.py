import pytest
import sqlite3
from helpers.database import Database
from managers.book_manager import BookManager

def test_search_by_id_and_title(client):
    conn=Database.connect(client.application.config['DATABASE'])
    try:
        assert len(BookManager.search_book(conn,'Mathematics','title'))==2
        assert BookManager.search_book(conn,'BK002','id')[0]['edition']==2
        assert BookManager.search_book(conn,'BK','id')==[]
    finally: conn.close()

def test_duplicate_book_rejected(client):
    conn=Database.connect(client.application.config['DATABASE'])
    try:
        with pytest.raises(sqlite3.IntegrityError):
            BookManager.add_book(conn,'BK001','Duplicate','Science',1,'Good')
    finally: conn.close()
