from agentic_evals import Eval, equals

def answer(country):
    return {"France": "Paris", "Japan": "Tokyo"}[country]

Eval("first-evaluation",
     data=[{"input": "France", "expected": "Paris"},
           {"input": "Japan", "expected": "Tokyo"}],
     task=answer,
     scores=[equals])

