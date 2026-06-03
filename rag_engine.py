"""
ContextAR - RAG Engine
Builds a FAISS vector store from exhibits_data.py and answers
questions using LangChain + OpenAI embeddings + GPT-4o.

Each response mode gets a tailored prompt so the LLM targets the
correct length and tone from the start — not post-hoc truncation.

Usage:
    # First run: build and save the index
    python rag_engine.py --build

    # Query
    python rag_engine.py --query "Who painted this blue swirly night scene?"
"""

import os
import argparse
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

from exhibits_data import EXHIBITS

load_dotenv()

FAISS_INDEX_PATH = "faiss_index"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL  = "gpt-4o"


# ---------------------------------------------------------------------------
# Mode-specific prompts
# ---------------------------------------------------------------------------
# Each prompt instructs the LLM to produce a response appropriate to the
# visitor's level of engagement and the environment they are standing in.

_BASE_CONTEXT = (
    "You are an audio guide for the exhibition "
    "'Western European Paintings, 15th–20th Century' at the Metropolitan Museum of Art. "
    "Use only the exhibit information below. "
    "Speak directly to the visitor as if they are standing in front of the painting.\n\n"
    "Exhibit information:\n{context}\n\n"
    "Visitor question: {question}\n\n"
)

# GLANCE_CARD — visitor is passing through a crowd, 5–15 s gaze
# Target: 1 punchy sentence, max ~20 words. No full stops mid-sentence.
PROMPT_GLANCE_CARD = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        _BASE_CONTEXT +
        "Answer in exactly ONE sentence (maximum 20 words). "
        "State only the single most surprising or memorable fact.\n\n"
        "Answer:"
    ),
)

# BRIEF_TEXT — visitor is interested, 5–15 s gaze, low crowd
# Target: 2–3 sentences, ~50 words.
PROMPT_BRIEF_TEXT = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        _BASE_CONTEXT +
        "Answer in 2–3 sentences (around 50 words). "
        "Give the key fact and one interesting detail. Be clear and engaging.\n\n"
        "Answer:"
    ),
)

# FULL_VOICE — visitor is deeply engaged, >15 s gaze, low crowd
# Target: full immersive guide, ~150 words, with historical context and story.
PROMPT_FULL_VOICE = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        _BASE_CONTEXT +
        "Answer in 4–6 sentences (around 120–150 words). "
        "Include: the direct answer to the question, relevant historical context, "
        "an interesting story or surprising detail, and a closing thought that invites "
        "the visitor to look more closely at the painting. Be warm and immersive.\n\n"
        "Answer:"
    ),
)

# BRIEF_TEXT_PROMPT — visitor engaged >15 s but environment is crowded
# Target: brief answer (~50 words) + a natural nudge toward a quieter spot.
PROMPT_BRIEF_TEXT_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        _BASE_CONTEXT +
        "Answer in 2–3 sentences (around 50 words). "
        "At the end, add one friendly sentence suggesting the visitor find a quieter spot "
        "for a more complete audio guide experience.\n\n"
        "Answer:"
    ),
)

_PROMPTS = {
    "GLANCE_CARD":        PROMPT_GLANCE_CARD,
    "BRIEF_TEXT":         PROMPT_BRIEF_TEXT,
    "FULL_VOICE":         PROMPT_FULL_VOICE,
    "BRIEF_TEXT_PROMPT":  PROMPT_BRIEF_TEXT_PROMPT,
}

# Fallback for any unrecognised mode
_DEFAULT_PROMPT = PROMPT_BRIEF_TEXT


# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

def build_index() -> FAISS:
    """Convert EXHIBITS list → LangChain Documents → FAISS index."""
    docs = []
    for exhibit in EXHIBITS:
        sections = {
            "key_facts":          exhibit.get("key_facts", ""),
            "visual_description": exhibit.get("visual_description", ""),
            "historical_context": exhibit.get("historical_context", ""),
            "technique":          exhibit.get("technique", ""),
            "story":              exhibit.get("story", ""),
            "summary":            exhibit.get("content", ""),
        }
        # Build one rich text block per exhibit
        text = (
            f"Name: {exhibit['name']}\n"
            f"Artist: {exhibit.get('artist', 'Unknown')}\n"
            f"Year: {exhibit.get('year', 'Unknown')}\n"
            f"Period: {exhibit['period']}\n\n"
            f"Key facts: {sections['key_facts']}\n\n"
            f"What you see: {sections['visual_description']}\n\n"
            f"Historical context: {sections['historical_context']}\n\n"
            f"Technique: {sections['technique']}\n\n"
            f"Story: {sections['story']}\n\n"
            f"Summary: {sections['summary']}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "id":     exhibit["id"],
                "name":   exhibit["name"],
                "artist": exhibit.get("artist", "Unknown"),
                "year":   exhibit.get("year", "Unknown"),
                "period": exhibit["period"],
            }
        ))

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"Index built: {len(docs)} exhibits saved to '{FAISS_INDEX_PATH}/'")
    return vectorstore


def load_index() -> FAISS:
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    return FAISS.load_local(
        FAISS_INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )


def get_or_build_index() -> FAISS:
    if os.path.exists(FAISS_INDEX_PATH):
        return load_index()
    return build_index()


# ---------------------------------------------------------------------------
# QA chain factory
# ---------------------------------------------------------------------------

def _build_qa_chain(vectorstore: FAISS, prompt: PromptTemplate) -> RetrievalQA:
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.3)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RAGEngine:
    """
    Singleton-style wrapper. Load once, query many times.

    Example:
        rag = RAGEngine()
        result = rag.query("What is the technique used here?", mode="FULL_VOICE")
        print(result["answer"])
        print(result["sources"])
    """

    def __init__(self):
        self._vectorstore = get_or_build_index()
        # Pre-build one QA chain per mode so we don't reconstruct on every call
        self._chains = {
            mode: _build_qa_chain(self._vectorstore, prompt)
            for mode, prompt in _PROMPTS.items()
        }

    def query(self, question: str, mode: str = "BRIEF_TEXT",
              max_length: int = None) -> dict:
        """
        Answer a visitor question using the knowledge base.

        Args:
            question:   natural language question
            mode:       response mode — selects the appropriate prompt.
                        One of: GLANCE_CARD | BRIEF_TEXT | FULL_VOICE | BRIEF_TEXT_PROMPT
            max_length: optional hard character cap (safety net; the prompt
                        already guides length so this should rarely trigger)

        Returns:
            {
                "answer":  str,
                "sources": list[str]   # exhibit names retrieved
            }
        """
        chain = self._chains.get(mode, self._chains["BRIEF_TEXT"])
        result = chain.invoke({"query": question})
        answer = result["result"].strip()

        if max_length and len(answer) > max_length:
            answer = answer[:max_length].rsplit(" ", 1)[0] + "…"

        scored = self._vectorstore.similarity_search_with_score(question, k=2)
        sources = [
            doc.metadata["name"]
            for doc, score in scored
            if score < 1.3
        ]
        return {"answer": answer, "sources": sources}

    def find_similar(self, exhibit_name: str, k: int = 2) -> list[str]:
        docs = self._vectorstore.similarity_search(exhibit_name, k=k)
        return [doc.metadata["name"] for doc in docs]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ContextAR RAG Engine")
    parser.add_argument("--build", action="store_true", help="Rebuild the FAISS index")
    parser.add_argument("--query", type=str, help="Ask a question")
    parser.add_argument("--mode",  type=str, default="BRIEF_TEXT",
                        choices=list(_PROMPTS.keys()),
                        help="Response mode (default: BRIEF_TEXT)")
    args = parser.parse_args()

    if args.build:
        build_index()

    if args.query:
        rag = RAGEngine()
        result = rag.query(args.query, mode=args.mode)
        print(f"\n[{args.mode}] Answer: {result['answer']}")
        print(f"Sources: {', '.join(result['sources'])}")

    if not args.build and not args.query:
        rag = RAGEngine()
        print("ContextAR RAG — type a question, Ctrl+C to quit\n")
        while True:
            try:
                q = input("Question: ").strip()
                if not q:
                    continue
                for m in _PROMPTS:
                    r = rag.query(q, mode=m)
                    print(f"\n  [{m}]\n  {r['answer']}")
                print()
            except KeyboardInterrupt:
                break
