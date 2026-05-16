"""
skills/base.py
The plugin mechanism. A "skill" is a self-contained, verified, native
Excel operation - the fast, reliable first layer the agent tries
before falling back to code generation.

This replaces the old pattern of "new function -> new schema block ->
register in TOOL_FUNCTIONS by hand" with a single decorator. Adding a
skill means writing one function in the skills/ folder and decorating
it - nothing else needs to change (Optional Plugin Architecture).
"""

SKILL_REGISTRY = {}  

def skill(name: str, description: str, input_schema: dict, category: str = "general"):
    """
    Decorator that registers a function as a skill.

    input_schema follows the same JSON-schema shape used for Claude/
    Gemini tool definitions, so registry.py can hand these straight to
    either provider with no translation step.
    """
    def decorator(func):
        SKILL_REGISTRY[name] = {
            "func": func,
            "description": description,
            "input_schema": input_schema,
            "category": category,
        }
        return func
    return decorator


def get_skill(name: str):
    return SKILL_REGISTRY.get(name)


def all_skills():
    return SKILL_REGISTRY
