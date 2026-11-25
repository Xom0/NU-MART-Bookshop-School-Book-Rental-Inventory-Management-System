"""Nu-Mart Bookshop — development entry point. Run: python app.py"""
import os
from flask import Flask
from config import DATABASE, SECRET_KEY
from helpers.database import Database
from routes.web import pages


def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(SECRET_KEY=SECRET_KEY,DATABASE=DATABASE,MAX_CONTENT_LENGTH=2*1024*1024)
    if test_config: app.config.update(test_config)
    Database.initialize(app.config['DATABASE'])
    app.teardown_appcontext(Database.close)
    app.register_blueprint(pages)
    return app


app=create_app()

if __name__=='__main__':
    app.run(debug=os.environ.get('NUMART_DEBUG','1')=='1',host='127.0.0.1')
