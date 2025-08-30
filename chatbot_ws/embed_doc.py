
import openai
import docx
import os
import json
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv
import time
load_dotenv()
# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

DOC_PATH = "SNM.docx"  # Update with your doc file path
EMBEDDINGS_PATH = "doc_embeddings.json"
MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500  # characters per chunk


# Extract Q&A pairs from docx (Q: ... A: ...)
def extract_qa_pairs(file_path):
    doc = docx.Document(file_path)
    qa_pairs = []
    current_q = None
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if (text.startswith('Q') or text.startswith('Q.')) and '?' in text:
            current_q = text
        elif (text.startswith('A') or text.startswith('A.')) and current_q:
            # Only add if both Q and A are non-empty
            if current_q.strip() and text.strip():
                qa_pairs.append((current_q.strip(), text.strip()))
            current_q = None
    return qa_pairs

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

def get_embedding(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.embeddings.create(
                input=[text],
                model=MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error for: {text[:60]}... | Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return []


def main():
    qa_pairs = extract_qa_pairs(DOC_PATH)
    embeddings = []
    for q, a in tqdm(qa_pairs, desc="Embedding Qs"):
        if not q or not a:
            print(f"Skipping empty Q or A: Q='{q}', A='{a}'")
            continue
        emb = get_embedding(q)
        if emb and isinstance(emb, list) and len(emb) > 0:
            embeddings.append({"question": q, "answer": a, "embedding": emb})
        else:
            print(f"Failed to embed: {q[:60]}... Skipping.")
    with open(EMBEDDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(embeddings, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(embeddings)} Q&A embeddings to {EMBEDDINGS_PATH}")

if __name__ == "__main__":
    main()