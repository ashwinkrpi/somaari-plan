"""mock_jev and mock_llm: no network. Used by tests (forced via SOMAARI_AI_MOCK=1)."""
import hashlib
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "jev"
RESPONDER = None   # tests may set: fn(state, questions) -> answers dict
LLM_RESPONDER = None  # tests may set: fn(prompt) -> str
CALLS = []


def fake_answers(questions, t=0.9, p="Medium", conf=0.9, m=0.1, d=0.1):
    """Build plausible answers for question ids by their prefix (t_, p_, m_, d_) or type."""
    out = {}
    for qid, q in questions.items():
        kind = q.get("type")
        if kind == "noul":
            v = {"t": t, "m": m, "d": d}.get(qid[:1], 0.5)
            out[qid] = {"type": "noul", "noul": v}
        elif kind == "choice":
            opts = list(q.get("criteria", {}))
            pick = p if p in opts else opts[0]
            probs = {o: (conf if o == pick else (1 - conf) / max(len(opts) - 1, 1)) for o in opts}
            out[qid] = {"type": "choice", "choice": pick, "probabilities": probs, "confidence": conf}
        else:
            out[qid] = {"type": "score", "score": 1.0, "legend": {}, "probabilities": {}, "confidence": conf}
    return out


def fixture_path(set_name, state):
    sha = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:8]
    return FIXTURES / f"{set_name}_{sha}.json"


def mock_jev(state, questions, set_name="adhoc"):
    CALLS.append(("jev", state))
    if RESPONDER:
        return RESPONDER(state, questions), {"input_tokens": 0}
    path = fixture_path(set_name, state)
    if not path.is_file():
        raise AssertionError(f"mock_jev: missing fixture {path.name}")
    return json.loads(path.read_text()), {"input_tokens": 0}


def mock_llm(prompt):
    CALLS.append(("llm", prompt))
    if LLM_RESPONDER:
        return LLM_RESPONDER(prompt)
    return '{"tasks": []}'
