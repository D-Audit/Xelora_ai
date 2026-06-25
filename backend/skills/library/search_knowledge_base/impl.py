"""
skills/library/search_knowledge_base/impl.py
Auto-migrated from skills/knowledge_skills.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

from knowledge.rag import KnowledgeBase, current_user_id


def run(query: str, top_k: int = 5):
    user_id = current_user_id()
    if not user_id:
        return {"status": "no_user_context", "verified": False,
                "verification_note": "No user_id was set for this task - knowledge base is per-user."}

    kb = KnowledgeBase(user_id)
    results = kb.search(query, top_k=top_k)
    return {"query": query, "results": results, "result_count": len(results), "verified": True}
