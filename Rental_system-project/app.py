from flask import Flask
from flask_cors import CORS
from blueprints.properties.properties import properties_bp 
from blueprints.users.users import users_bp   
from blueprints.reviews.reviews import reviews_bp
from blueprints.auth.auth import auth_bp
import globals
import os

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Uses SECRET_KEY from globals.py
app.config['SECRET_KEY'] = globals.SECRET_KEY  

#Ensure the upload folder exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Registering Blueprints
app.register_blueprint(properties_bp)  
app.register_blueprint(users_bp)  
app.register_blueprint(reviews_bp)
app.register_blueprint(auth_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001)  
