from flask import Blueprint, request, jsonify, make_response
from decorators import jwt_required, admin_required
from bson import ObjectId
import jwt
import bcrypt
import datetime
import globals
from bson.errors import InvalidId

users_bp = Blueprint('users_bp', __name__)

users = globals.db.users  # MongoDB Users Collection
blacklist = globals.db.blacklist  # Token blacklist collection


#for registering a new user
@users_bp.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.json

        # Ensures required fields
        if not all(key in data for key in ["username", "password", "role"]):
            return make_response(jsonify({"error": "Username, password, and role are required"}), 400)

        # Check if user already exists
        if users.find_one({"username": data["username"]}):
            return make_response(jsonify({"error": "Username already exists"}), 409)

        # Hash password
        hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt())

        # Inserts user
        user_data = {
            "username": data["username"],
            "password": hashed_password,
            "role": data["role"]  # Role can be admin, owner, or tenant
        }
        users.insert_one(user_data)

        return make_response(jsonify({"message": "User registered successfully"}), 201)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)



# get current users details 
@users_bp.route('/me', methods=['GET'])
@jwt_required
def get_current_user():
    try:
        user = users.find_one({'_id': ObjectId(request.user['user_id'])}, {"password": 0})  # Excludes password
        if user:
            user["_id"] = str(user["_id"])
            return make_response(jsonify(user), 200)

        return make_response(jsonify({'message': 'User not found'}), 404)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


# Admin delete user
@users_bp.route('/users/delete/<string:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    try:
        # Validate ObjectId format
        try:
            user_oid = ObjectId(user_id)
        except InvalidId:
            return make_response(jsonify({"error": "Invalid user ID format"}), 400)

        # Find and delete the user
        result = users.delete_one({"_id": user_oid})

        if result.deleted_count == 0:
            return make_response(jsonify({"error": "User not found"}), 404)

        return make_response(jsonify({"message": "User deleted successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


# Admin update user role
@users_bp.route('/users/update-role/<string:user_id>', methods=['PUT'])
@admin_required  
def update_user_role(user_id):
    try:
        data = request.json
        new_role = data.get("role")

        if new_role not in ["admin", "owner", "tenant"]:
            return make_response(jsonify({"error": "Invalid role"}), 400)

        # Validate ObjectId format
        try:
            user_oid = ObjectId(user_id)
        except InvalidId:
            return make_response(jsonify({"error": "Invalid user ID format"}), 400)

        result = users.update_one({"_id": user_oid}, {"$set": {"role": new_role}})

        if result.modified_count == 0:
            return make_response(jsonify({"error": "User not found or no changes made"}), 404)

        return make_response(jsonify({"message": "User role updated successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#Admin get all users
@users_bp.route('/users/all', methods=['GET'])
@admin_required
def get_all_users():
    try:
        users_list = list(users.find({}, {"password": 0}))  # Excludes passwords
        for user in users_list:
            user["_id"] = str(user["_id"])

        return make_response(jsonify(users_list), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)
