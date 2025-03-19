from flask import request, jsonify, make_response
import jwt
from functools import wraps
import globals

blacklist = globals.db.blacklist  # MongoDB blacklist collection


#HELPER FUNCTION: Extract Token from Header 
def extract_token():
    """Extracts JWT token from request headers."""
    token = request.headers.get('x-access-token') or request.headers.get('Authorization')

    if token and token.startswith("Bearer "):  # Supports "Authorization: Bearer <token>"
        token = token.split(" ")[1]  # Extract actual token

    return token


# JWT authentication decorator
def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        token = extract_token()
        if not token:
            return make_response(jsonify({'message': 'Token is missing'}), 401)
        
        try:
            data = jwt.decode(token, globals.SECRET_KEY, algorithms=['HS256'])

            # Checks if token is blacklisted
            if blacklist.find_one({'token': token}):
                return make_response(jsonify({'message': 'Token is invalid (blacklisted)'}), 401)

            request.user = data  # Stores decoded token data in request object
            
        except jwt.ExpiredSignatureError:
            return make_response(jsonify({'message': 'Token has expired'}), 401)
        except jwt.InvalidTokenError:
            return make_response(jsonify({'message': 'Token is invalid'}), 401)
        
        return func(*args, **kwargs)
    
    return jwt_required_wrapper


# Role-based access decorator
def role_required(required_roles):
    """Decorator to restrict access based on user roles."""
    def decorator(func):
        @wraps(func)
        def role_required_wrapper(*args, **kwargs):
            token = extract_token()
            if not token:
                return make_response(jsonify({'message': 'Token is missing'}), 401)
            
            try:
                data = jwt.decode(token, globals.SECRET_KEY, algorithms=['HS256'])

                # Ensure the user has one of the required roles
                if data.get('role') not in required_roles:
                    return make_response(jsonify({'message': 'Access denied: Insufficient permissions'}), 403)

                request.user = data  # Store decoded data in request object

            except jwt.ExpiredSignatureError:
                return make_response(jsonify({'message': 'Token has expired'}), 401)
            except jwt.InvalidTokenError:
                return make_response(jsonify({'message': 'Token is invalid'}), 401)

            return func(*args, **kwargs)
        
        return role_required_wrapper
    
    return decorator


#Specific role decorators
admin_required = role_required(['admin'])  # Only admins can access
owner_required = role_required(['admin', 'owner'])  # Admins and Owners can access
tenant_required = role_required(['admin', 'owner', 'tenant'])  # All users can access
