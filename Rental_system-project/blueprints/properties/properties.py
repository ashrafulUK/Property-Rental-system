from flask import Blueprint, request, jsonify, make_response
from decorators import jwt_required, owner_required, admin_required, tenant_required
from bson import ObjectId
import globals
import os
from werkzeug.utils import secure_filename

properties_bp = Blueprint('properties_bp', __name__)

properties = globals.db.properties  #mongoDB properties collection
users = globals.db.users  # MongoDB Users Collection

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Checks if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#To get all properties with pagination
@properties_bp.route('/properties', methods=['GET'])
def get_all_properties():
    try:
        page = int(request.args.get('page', 1))  
        page_size = int(request.args.get('page_size', 10))  
        skip = (page - 1) * page_size  

        properties_cursor = properties.find().skip(skip).limit(page_size)
        data_to_return = []

        for property in properties_cursor:
            property['_id'] = str(property['_id'])  # Convert ObjectId to String
            property['views'] = property.get('views', 0)

            # Include location details in response
            if "location" in property:
                property['location_name'] = property['location'].get('name', 'Unknown') 
                property['latitude'] = property['location']['coordinates'][1]
                property['longitude'] = property['location']['coordinates'][0]
                del property['location']  

            # Converts nested ObjectId fields inside reviews
            if "reviews" in property:
                for review in property["reviews"]:
                    review["_id"] = str(review["_id"])  # Convert Review ObjectId to String
                    review["user_id"] = str(review["user_id"])  # Convert user_id to string

            data_to_return.append(property)

        return make_response(jsonify(data_to_return), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#Create a new property
@properties_bp.route('/properties', methods=['POST'])
@owner_required  
def create_property():
    try:
        data = request.json

        required_fields = ["owner_name", "property_type", "rental_price", "bedrooms", "bathrooms", "latitude", "longitude", "location_name"]
        if not all(field in data for field in required_fields):
            return make_response(jsonify({'error': 'Missing required fields'}), 400)

        property_data = {
            "owner_name": data.get("owner_name"),
            "property_type": data.get("property_type"),
            "location": {
                "name": data.get("location_name"),  # Stores location name 
                "type": "Point",
                "coordinates": [float(data["longitude"]), float(data["latitude"])]  # GeoJSON format
            },
            "rental_price": data.get("rental_price"),
            "bedrooms": data.get("bedrooms"),
            "bathrooms": data.get("bathrooms"),
            "availability_status": data.get("availability_status", "available"),
            "views": 0  
        }

        result = properties.insert_one(property_data)
        return make_response(jsonify({"message": "Property added successfully", "property_id": str(result.inserted_id)}), 201)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#for uploading property image ( this feature is only for the frontend development)
@properties_bp.route('/properties/<string:property_id>/upload', methods=['POST'])
@owner_required  
def upload_property_image(property_id):
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        properties.update_one(
            {"_id": ObjectId(property_id)},
            {"$set": {"image_url": f"/uploads/{filename}"}}
        )

        return jsonify({"message": "Image uploaded successfully", "image_url": f"/uploads/{filename}"}), 201

    return jsonify({"error": "Invalid file format"}), 400

#Searching properties with filters
@properties_bp.route('/properties/search', methods=['GET'])
def search_properties():
    try:
        query = {}

        if 'location' in request.args:
            query['location.name'] = {'$regex': request.args['location'], '$options': 'i'}
        
        if 'min_price' in request.args and 'max_price' in request.args:
            query['rental_price'] = {
                "$gte": float(request.args['min_price']),
                "$lte": float(request.args['max_price'])
            }

        if 'bedrooms' in request.args:
            query['bedrooms'] = int(request.args['bedrooms'])

        if 'bathrooms' in request.args:
            query['bathrooms'] = int(request.args['bathrooms'])

        if 'availability_status' in request.args:
            query['availability_status'] = request.args['availability_status']

        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size

        properties_cursor = properties.find(query).skip(skip).limit(page_size).sort("rental_price", 1)
        data_to_return = []

        for property in properties_cursor:
            property['_id'] = str(property['_id'])  # Convert ObjectId to string
            property['views'] = property.get('views', 0)

            # Convert ObjectId inside reviews
            if "reviews" in property:
                for review in property["reviews"]:
                    review["_id"] = str(review["_id"])
                    review["user_id"] = str(review["user_id"])

            # Include location details in response
            if "location" in property:
                property["location_name"] = property["location"].get("name", "Unknown")  # Ensure location name exists
                property["latitude"] = property["location"]["coordinates"][1]
                property["longitude"] = property["location"]["coordinates"][0]
                del property["location"]  # Remove raw GeoJSON format

            data_to_return.append(property)

        return make_response(jsonify(data_to_return), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Invalid request", "details": str(e)}), 400)


#Updates a property only by the owner
@properties_bp.route('/properties/<string:property_id>', methods=['PUT'])
@owner_required
def update_property(property_id):
    try:
        data = request.json
        update_fields = {}

        if "rental_price" in data:
            update_fields["rental_price"] = data["rental_price"]
        if "bedrooms" in data:
            update_fields["bedrooms"] = data["bedrooms"]
        if "bathrooms" in data:
            update_fields["bathrooms"] = data["bathrooms"]
        if "availability_status" in data:
            update_fields["availability_status"] = data["availability_status"]
        if "latitude" in data and "longitude" in data and "location_name" in data:
            update_fields["location"] = {
                "name": data["location_name"],  # Allow updating location name
                "type": "Point",
                "coordinates": [float(data["longitude"]), float(data["latitude"])]
            }

        if not update_fields:
            return make_response(jsonify({'error': 'No valid fields to update'}), 400)

        result = properties.update_one({"_id": ObjectId(property_id)}, {"$set": update_fields})

        if result.modified_count == 0:
            return make_response(jsonify({"message": "No changes made or property not found"}), 404)

        return make_response(jsonify({"message": "Property updated successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)


#Getting a single property with the property_id
@properties_bp.route('/properties/<string:property_id>', methods=['GET'])
def get_property(property_id):
    try:
        # Convert property_id to ObjectId
        try:
            property_oid = ObjectId(property_id)
        except:
            return make_response(jsonify({"error": "Invalid property ID format"}), 400)

        property = properties.find_one({"_id": property_oid})
        if not property:
            return make_response(jsonify({"error": "Property not found"}), 404)

        # Increment views count
        properties.update_one({"_id": property_oid}, {"$inc": {"views": 1}})

        # Convert ObjectId to String
        property["_id"] = str(property["_id"])
        property["views"] = property.get("views", 0) + 1

        # Convert nested ObjectId fields inside reviews
        if "reviews" in property:
            for review in property["reviews"]:
                review["_id"] = str(review["_id"])  # Convert Review ID
                review["user_id"] = str(review["user_id"])  # Convert User ID

        # Include location details in response
        if "location" in property:
            property["location_name"] = property["location"].get("name", "Unknown")  # Ensure location name exists
            property["latitude"] = property["location"]["coordinates"][1]
            property["longitude"] = property["location"]["coordinates"][0]
            del property["location"]  # Remove raw GeoJSON format

        return make_response(jsonify(property), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)
    
#Deleting a property only by the owner and admin
@properties_bp.route('/properties/<string:property_id>', methods=['DELETE'])
@jwt_required  # Ensure user is logged in
def delete_property(property_id):
    try:
        # Debugging: Print user data from token
        print("Decoded JWT User Data:", request.user)

        # Extract user role and ID from token
        user_role = request.user.get('role')
        user_id = request.user.get('user_id')
        user_name = request.user.get('username')

        # Convert property_id to ObjectId
        try:
            property_oid = ObjectId(property_id)
        except:
            return make_response(jsonify({"error": "Invalid property ID format"}), 400)

        # Find the property
        property = properties.find_one({"_id": property_oid})
        if not property:
            return make_response(jsonify({"error": "Property not found"}), 404)

        # Debugging: Print the property details
        print("Property Data:", property)

        # Admins can delete any property
        if user_role == "admin":
            properties.delete_one({"_id": property_oid})
            return make_response(jsonify({"message": "Property deleted successfully by Admin"}), 200)

        # Owners can only delete their own properties
        if user_role == "owner":
            stored_owner_name = property.get("owner_name", "").strip().lower()  # Convert to lowercase
            user_name_check = user_name.strip().lower()  # Convert to lowercase

            print(f"Stored Owner Name: {stored_owner_name}, Requesting User: {user_name_check}")

            if stored_owner_name == user_name_check:
                properties.delete_one({"_id": property_oid})
                return make_response(jsonify({"message": "Property deleted successfully by Owner"}), 200)
            else:
                return make_response(jsonify({"error": "Unauthorized: You can only delete your own properties"}), 403)

        return make_response(jsonify({"error": "Unauthorized: You can only delete your own properties"}), 403)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)
