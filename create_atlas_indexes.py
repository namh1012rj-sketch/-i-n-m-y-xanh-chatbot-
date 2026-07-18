import os
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

def create_indexes():
    client = MongoClient(os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0"))
    db = client["dienmayxanh_db"]
    products_col = db["products"]
    
    print("Creating Text Search Index (default)...")
    try:
        text_index = SearchIndexModel(
            definition={
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "name": {
                            "type": "string",
                            "analyzer": "lucene.vietnamese"
                        },
                        "promotion": {
                            "type": "string",
                            "analyzer": "lucene.vietnamese"
                        }
                    }
                }
            },
            name="default"
        )
        products_col.create_search_index(text_index)
        print("Text Search Index creation initiated!")
    except Exception as e:
        print(f"Error creating Text Search Index: {e}")

    print("Creating Vector Search Index (vector_index)...")
    try:
        vector_index = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 1024,
                        "similarity": "cosine"
                    }
                ]
            },
            name="vector_index",
            type="vectorSearch"
        )
        products_col.create_search_index(vector_index)
        print("Vector Search Index creation initiated!")
    except Exception as e:
        print(f"Error creating Vector Search Index: {e}")

    print("Creating Vector Search Index for FAQ (vector_index_faq)...")
    try:
        faq_col = db["faq"]
        faq_vector_index = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 1024,
                        "similarity": "cosine"
                    }
                ]
            },
            name="vector_index_faq",
            type="vectorSearch"
        )
        faq_col.create_search_index(faq_vector_index)
        print("FAQ Vector Search Index creation initiated!")
    except Exception as e:
        print(f"Error creating FAQ Vector Search Index: {e}")

if __name__ == "__main__":
    create_indexes()
