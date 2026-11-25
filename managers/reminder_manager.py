from datetime import date,datetime,timedelta

class ReminderManager:
    @staticmethod
    def check_due_dates(conn, today=None):
        today=today or date.today()
        upcoming=(today+timedelta(days=7)).isoformat()
        records=conn.execute("""SELECT r.*, s.first_name,s.last_name,b.title FROM rentals r
            JOIN students s ON r.student_id=s.student_id JOIN books b ON b.book_id=r.book_id
            WHERE r.status='Active' AND r.due_date<=? ORDER BY r.due_date,r.rental_id""",(upcoming,))
        result=[]
        for row in records:
            item=dict(row)
            item['label']='Overdue' if item['due_date']<today.isoformat() else 'Due soon'
            result.append(item)
        return result

    @staticmethod
    def find_overdue(conn, today=None):
        today=today or date.today()
        return [x for x in ReminderManager.check_due_dates(conn,today) if x['label']=='Overdue']

    @staticmethod
    def create_reminder(conn, rental_id, today=None):
        today=today or date.today()
        rental=conn.execute("""SELECT r.*,b.title FROM rentals r JOIN books b ON b.book_id=r.book_id WHERE rental_id=?""",(rental_id,)).fetchone()
        if not rental or rental['status']!='Active': raise ValueError('An active rental is required.')
        due=date.fromisoformat(rental['due_date'])
        if due > today+timedelta(days=7): raise ValueError('This rental is not due within seven days.')
        label='OVERDUE' if due<today else 'DUE SOON'
        message=f'{label}: {rental["title"]} ({rental["book_id"]}) — due {rental["due_date"]}'
        conn.execute("""INSERT OR IGNORE INTO reminders(rental_id,message,created_at,status)
              VALUES(?,?,?,'Generated')""",(rental_id,message,datetime.now().isoformat(timespec='seconds')))
        return message
