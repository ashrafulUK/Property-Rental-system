from flask import Blueprint, request, jsonify, make_response
from bson import ObjectId
import globals
import datetime
from decorators import jwt_required, admin_required
from bson.errors import InvalidId #imports the InvalidId error from bson

reviews_bp = Blueprint('reviews_bp', __name__)

properties = globals.db.properties  # Using the correct collection


#Getting all reviews for a property
@reviews_bp.route('/properties/<string:property_id>/reviews', methods=['GET'])
def get_reviews(property_id):
    try:
        property = properties.find_one({'_id': ObjectId(property_id)}, {'reviews': 1, '_id': 0, 'average_rating': 1})
        
        if not property:
            return make_response(jsonify({"error": "Property not found"}), 404)

        reviews = property.get('reviews', [])  # Get reviews if they exist
        
        for review in reviews:
            review['_id'] = str(review['_id'])  # Convert MongoDB ObjectId to string

        return make_response(jsonify({
            "average_rating": property.get("average_rating", 0),  # Ensure average rating is included
            "reviews": reviews
        }), 200)

    except Exception:
        return make_response(jsonify({"error": "Invalid property ID format"}), 400)
    

#Add a new review to a property
@reviews_bp.route('/properties/<string:property_id>/reviews', methods=['POST'])
@jwt_required  
def add_review(property_id):
    try:
        data = request.json
        required_fields = ["rating", "comment"]

        # Check if all required fields are provided
        if not all(field in data for field in required_fields):
            return make_response(jsonify({"error": "Missing required fields"}), 400)

        # Validate rating is between 1 and 5
        if not isinstance(data["rating"], int) or not (1 <= data["rating"] <= 5):
            return make_response(jsonify({"error": "Rating must be an integer between 1 and 5"}), 400)

        # Convert property_id to ObjectId
        try:
            property_oid = ObjectId(property_id)
        except InvalidId:
            return make_response(jsonify({"error": "Invalid property ID format"}), 400)

        # Check if the property exists
        property = properties.find_one({"_id": property_oid})
        if not property:
            return make_response(jsonify({"error": "Property not found"}), 404)

        # Create the review object
        review = {
            "_id": ObjectId(),  # Generate a unique ObjectId for the review
            "user": request.user["username"],
            "user_id": request.user["user_id"],  
            "rating": data["rating"],
            "comment": data["comment"],
            "created_at": datetime.datetime.utcnow()
        }

        # Push the review inside the `reviews` array of the correct property
        result = properties.update_one({"_id": property_oid}, {"$push": {"reviews": review}})

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to add review"}), 500)

        # Recalculate average rating
        recalculate_average_rating(property_id)

        return make_response(jsonify({"message": "Review added successfully", "review_id": str(review["_id"])}), 201)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)

#Update a review by the user who posted it
@reviews_bp.route('/properties/<string:property_id>/reviews/<string:review_id>', methods=['PUT'])
@jwt_required  
def update_review(property_id, review_id):
    try:
        # Sanitize ID input
        property_id = property_id.strip()
        review_id = review_id.strip()

        # Validate ObjectId format
        try:
            property_oid = ObjectId(property_id)
            review_oid = ObjectId(review_id)
        except InvalidId:
            return make_response(jsonify({"error": "Invalid property ID or review ID format"}), 400)

        data = request.json
        update_fields = {}

        # Ensure rating is an integer between 1 and 5
        if "rating" in data:
            if not isinstance(data["rating"], int) or not (1 <= data["rating"] <= 5):
                return make_response(jsonify({"error": "Rating must be an integer between 1 and 5"}), 400)
            update_fields["reviews.$.rating"] = data["rating"]

        if "comment" in data:
            update_fields["reviews.$.comment"] = data["comment"]

        if not update_fields:
            return make_response(jsonify({"error": "No valid fields to update"}), 400)

        # Find the property and the specific review
        property = properties.find_one({"_id": property_oid, "reviews._id": review_oid}, {"reviews": 1})

        if not property:
            return make_response(jsonify({"error": "Property or Review not found"}), 404)

        # Find the review to update
        review_to_update = None
        for review in property["reviews"]:
            if review["_id"] == review_oid:
                review_to_update = review
                break

        if not review_to_update:
            return make_response(jsonify({"error": "Review not found"}), 404)

        # Only allow the user who posted the review to update it
        if request.user["user_id"] != review_to_update["user_id"]:
            return make_response(jsonify({"error": "Unauthorized: Only the review owner can update this review"}), 403)

        # Update the review using the correct query
        result = properties.update_one(
            {"_id": property_oid, "reviews._id": review_oid},
            {"$set": update_fields}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Review update failed"}), 500)

        # Recalculate the average rating after update
        recalculate_average_rating(property_id)

        return make_response(jsonify({"message": "Review updated successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Internal Server Error", "details": str(e)}), 500)

#Delete a review by the user who posted it or an admin
@reviews_bp.route('/properties/<string:property_id>/reviews/<string:review_id>', methods=['DELETE'])
@jwt_required  
def delete_review(property_id, review_id):
    try:
        # Validate ObjectId format
        try:
            property_oid = ObjectId(property_id)
            review_oid = ObjectId(review_id)
        except InvalidId:
            return make_response(jsonify({"error": "Invalid property ID or review ID format"}), 400)

        # Find the property and the review
        property = properties.find_one({"_id": property_oid}, {"reviews": 1})
        
        if not property or "reviews" not in property:
            return make_response(jsonify({"error": "Property not found"}), 404)

        # Debugging: Print stored review IDs
        print(f"Stored review IDs in MongoDB: {[str(review['_id']) for review in property['reviews']]}")
        print(f"Review ID to delete: {review_id}")

        # Find the review in the property
        review_to_delete = next((review for review in property["reviews"] if str(review["_id"]) == str(review_oid)), None)

        if not review_to_delete:
            return make_response(jsonify({"error": "Review not found"}), 404)

        # Check if the user is authorized (either the review owner or an admin)
        if request.user["role"] != "admin" and request.user["user_id"] != review_to_delete["user_id"]:
            return make_response(jsonify({"error": "Unauthorized: Only the review owner or an admin can delete this review"}), 403)

        # Remove the review
        result = properties.update_one({"_id": property_oid}, {"$pull": {"reviews": {"_id": review_oid}}})

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Review deletion failed"}), 500)

        # Recalculate the average rating after deletion
        recalculate_average_rating(property_id)

        return make_response(jsonify({"message": "Review deleted successfully"}), 200)

    except Exception as e:
        return make_response(jsonify({"error": "Invalid request", "details": str(e)}), 400)

#Helper function to recalculate the average rating of a property
def recalculate_average_rating(property_id):
    try:
        property = properties.find_one({"_id": ObjectId(property_id)}, {"reviews": 1})

        if not property or "reviews" not in property or not property["reviews"]:
            properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"average_rating": 0}})
            return

        total_rating = sum(review["rating"] for review in property["reviews"])
        review_count = len(property["reviews"])
        average_rating = round(total_rating / review_count, 1)  # Round to 1 decimal place

        properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"average_rating": average_rating}})

    except Exception as e:
        print(f"Error recalculating average rating: {e}")
