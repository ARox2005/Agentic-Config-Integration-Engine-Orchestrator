import os
import json
from pathlib import Path
from langchain_chroma import Chroma
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings

# Define where ChromaDB will save its data locally
CHROMA_PERSIST_DIR = Path(__file__).parent.parent / "data" / "chromadb"

# We initialize a local embedding model. 
# "all-MiniLM-L6-v2" is a small, extremely fast model perfect for encoding SOW text vs Adapter Profiles.
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Initialize the Chroma database collection
vector_db = Chroma(
    collection_name="adapter_profiles",
    embedding_function=embedding_model,
    persist_directory=str(CHROMA_PERSIST_DIR)
)

def upsert_adapter_profile(profile_dict: dict) -> None:
    """
    Takes an adapter profile dictionary, converts it to a searchable document, 
    and inserts or updates it in the Chroma database.
    """
    adapter_name = profile_dict.get("name")
    if not adapter_name:
        return
    
    # We create a rich text representation of the adapter for the AI to "read"
    # This string is what actually gets mathematically embedded.
    document_text = (
        f"Adapter Name: {adapter_name}\n"
        f"Category: {profile_dict.get('category', 'General')}\n"
        f"Provider: {profile_dict.get('provider', '')}\n"
        f"Description: {profile_dict.get('description', '')}\n"
        f"Supported Actions: {', '.join(profile_dict.get('supported_actions', []))}\n"
        f"Mandatory Fields: {', '.join(profile_dict.get('data_schema', {}).get('mandatory_fields', []))}\n"
    )
    
    # We store the raw JSON as metadata so we can reconstruct it exactly later
    metadata = {"profile_json": json.dumps(profile_dict)}
    
    # Insert or Update the embedding in Chroma. 
    # We use the adapter's name as a unique ID to prevent duplicates.
    vector_db.add_texts(
        texts=[document_text],
        metadatas=[metadata],
        ids=[adapter_name]
    )
    print(f"[VECTOR_DB] Upserted profile for adapter: {adapter_name}")

def search_similar_adapters(sow_text: str, top_k: int = 3) -> list:
    """
    Takes the raw SOW text and finds the Top K most semantically similar adapter profiles.
    Returns the original profile dictionaries.
    """
    # The search returns a list of LangChain Document objects
    results = vector_db.similarity_search(query=sow_text, k=top_k)
    
    matched_profiles = []
    for doc in results:
        # Extract the original JSON profile from the document's metadata
        profile_json_str = doc.metadata.get("profile_json")
        if profile_json_str:
            matched_profiles.append(json.loads(profile_json_str))
            
    return matched_profiles
