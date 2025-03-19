from flask import Blueprint, request, jsonify, make_response
import jwt
import datetime
import bcrypt
import globals
from decorators import jwt_required

auth_bp = Blueprint('auth_bp', __name__)

blacklist = globals.db.blacklist
users = globals.db.users

#Login endpoint
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        auth = request.json  
        if not auth or not auth.get('username') or not auth.get('password'):
            return make_response(jsonify({'error': 'Username and password are required'}), 400)

        user = users.find_one({'username': auth['username']})
        if user:
           
            print(f"User '{auth['username']}' is logging in with role: {user.get('role')}")

            #hashed password check
            if bcrypt.checkpw(auth['password'].encode('utf-8'), user['password']):
                token = jwt.encode({
                    'user_id': str(user['_id']),
                    'username': user['username'],
                    'role': user.get('role', 'tenant'),  # Default to tenant if role is missing
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                }, globals.SECRET_KEY, algorithm='HS256')

                return make_response(jsonify({'token': token}), 200)
            else:
                return make_response(jsonify({'error': 'Invalid password'}), 401)

        return make_response(jsonify({'error': 'User not found'}), 404)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#Logout endpoint
@auth_bp.route('/logout', methods=['POST'])
@jwt_required
def logout():
    try:
        token = request.headers.get('x-access-token')
        if not token:
            return make_response(jsonify({'error': 'Token required'}), 400)

        # check of the token if its already blacklisted
        if blacklist.find_one({'token': token}):
            return make_response(jsonify({'error': 'Token already blacklisted'}), 400)

        # Inserting into blacklist
        blacklist.insert_one({'token': token})
        return make_response(jsonify({'message': 'Successfully logged out'}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#Password hashing
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


#Password verification
def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password)
