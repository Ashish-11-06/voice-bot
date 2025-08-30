import openai
import docx
import os
import json
import numpy as np
from tqdm import tqdm

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

DOC_PATH = "your_doc_file.docx"  # Update with your doc file path
EMBEDDINGS_PATH = "doc_embeddings.json"
MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500  # characters per chunk

def read_docx(file_path):
    doc = docx.Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    return "\n".join(full_text)

def chunk_text(text, chunk_size=CHUNK_SIZE):
    paragraphs = text.split('\n')
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < chunk_size:
            current += " " + para
        else:
            if current:
                chunks.append(current.strip())
            current = para
    if current:
        chunks.append(current.strip())
    return chunks

def get_embedding(text):
    response = openai.embeddings.create(
        input=[text],
        model=MODEL
    )
    return response.data[0].embedding

def main():
    text = read_docx(DOC_PATH)
    chunks = chunk_text(text)
    embeddings = []
    for chunk in tqdm(chunks, desc="Embedding chunks"):
        emb = get_embedding(chunk)
        embeddings.append({"text": chunk, "embedding": emb})
    with open(EMBEDDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(embeddings, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(embeddings)} embeddings to {EMBEDDINGS_PATH}")

if __name__ == "__main__":
    main()