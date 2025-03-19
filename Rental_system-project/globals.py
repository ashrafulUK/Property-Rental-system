from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client.property_rental_db # Database name

SECRET_KEY = 'mysecret'

