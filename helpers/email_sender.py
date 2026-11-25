"""Optional email delivery. Demo mode does not send real student messages."""
import smtplib
from email.message import EmailMessage

class EmailSender:
    @staticmethod
    def send_email(to_address, subject, message, host=None, port=587, username=None, password=None, sender=None):
        if not all((host,username,password,sender,to_address)):
            raise ValueError('Email delivery is not configured. A reminder can still be generated locally.')
        email=EmailMessage()
        email['To']=to_address
        email['From']=sender
        email['Subject']=subject
        email.set_content(message)
        with smtplib.SMTP(host,port,timeout=15) as server:
            server.starttls()
            server.login(username,password)
            server.send_message(email)
