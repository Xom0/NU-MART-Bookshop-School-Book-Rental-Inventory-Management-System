from datetime import date,timedelta
from helpers.database import Database
from managers.rental_manager import RentalManager
from managers.reminder_manager import ReminderManager

def test_overdue_and_reminder_creation(client):
    conn=Database.connect(client.application.config['DATABASE'])
    try:
        user=conn.execute("SELECT user_id FROM users WHERE username='admin'").fetchone()[0]
        old=date.today()-timedelta(days=10)
        due=old+timedelta(days=3)
        RentalManager.rent_book(conn,'ST001',['BK001'],due.isoformat(),user,today=old)
        overdue=ReminderManager.find_overdue(conn)
        assert len(overdue)==1 and overdue[0]['label']=='Overdue'
        message=ReminderManager.create_reminder(conn,overdue[0]['rental_id'])
        assert message.startswith('OVERDUE')
        assert conn.execute('SELECT count(*) FROM reminders').fetchone()[0]==1
    finally: conn.close()
