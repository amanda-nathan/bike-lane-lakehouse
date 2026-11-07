"""Text-to-SQL vs. semantic layer: does the answer come out right, and does it make the point it should?

Claude answers each question twice, connected to the MCP server:

    sql_only        describe_tables + run_sql
    semantic_first  all four tools, told to prefer list_metrics + query_metrics

Expected answers come from each question's reference SQL, run against Trino at eval time.

    uv run --group eval python evals/run_eval.py --dry-run
    uv run --group eval python evals/run_eval.py --questions questions_hard.yml --repeats 3
    uv run --group eval python evals/run_eval.py --model claude-haiku-5-5
"""

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import yaml
from anthropic.lib.tools.mcp import async_mcp_tool
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from bikelake import warehouse

EVAL_DIR = Path(__file__).resolve().parent
load_dotenv(EVAL_DIR.parent / ".env")  # ANTHROPIC_API_KEY

MODEL = "claude-opus-5-5"
JUDGE_MODEL = "claude-opus-5-5"
# $ per million tokens (input, output), for the cost report.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
# Server-side fallback on a declined request. Haiku 5.5 doesn't support it.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}

COMMON = """\
You answer questions about Boston and New York City bike, traffic, and crash data using the tools.
Look the numbers up; don't answer from memory.

Explain the answer briefly, including anything about the data a reader should know before relying
on the number. End with a final line in the form

ANSWER: <number>

giving the single number asked for. Give fractions and changes as decimals (0.17, not 17%)."""

ARMS = {
    "sql_only": {
        "tools": {"describe_tables", "run_sql"},
        "system": COMMON + "\n\nCall describe_tables first, then query with run_sql (Trino SQL).",
    },
    "semantic_first": {
        "tools": {"list_metrics", "query_metrics", "describe_tables", "run_sql"},
        "system": COMMON
        + "\n\nPrefer the metrics: call list_metrics, then query_metrics. Metrics carry caveats; pass them on."
        + " Use describe_tables and run_sql only when no metric fits.",
    },
}

JUDGE_PROMPT = """\
A data question was answered by an assistant. Decide whether the answer makes the required point.
Any wording counts if the meaning is there. A vague hedge ("data may have limitations") does not.

Question: {question}

Required point: {point}

Answer:
{answer}"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"makes_point": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["makes_point", "reason"],
    "additionalProperties": False,
}

ANSWER = re.compile(r"ANSWER:\s*\**\s*(-?[\d,]*\.?\d+(?:e-?\d+)?)\s*(%?)", re.IGNORECASE)


def load_questions(path: Path, limit: int | None) -> list[dict]:
    questions = yaml.safe_load(path.read_text())[:limit]
    for q in questions:
        sqls = [q["reference_sql"], *q.get("accepted_sql", [])]
        q["expected"] = [float(warehouse.run(s)["rows"][0][0]) for s in sqls]
    return questions


def parse_answer(text: str) -> float | None:
    matches = ANSWER.findall(text)
    if not matches:
        return None
    number, percent = matches[-1]
    value = float(number.replace(",", ""))
    return value / 100 if percent else value


def is_correct(q: dict, got: float | None) -> bool:
    if got is None:
        return False
    for expected in q["expected"]:
        if "abs_tolerance" in q:
            if abs(got - expected) <= q["abs_tolerance"]:
                return True
        elif abs(got - expected) <= q.get("tolerance", 0.01) * abs(expected):
            return True
    return False


async def makes_point(client, q: dict, text: str) -> tuple[bool | None, dict]:
    """Model-graded when the question has must_mention; keyword match for caveat_keywords; else None."""
    if "must_mention" in q:
        response = await client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(question=q["question"], point=q["must_mention"], answer=text)}],
        )
        verdict = json.loads(next(b.text for b in response.content if b.type == "text"))
        return verdict["makes_point"], {"judge_reason": verdict["reason"], "judge_usage": response.usage.model_dump()}
    if "caveat_keywords" in q:
        return any(k.lower() in text.lower() for k in q["caveat_keywords"]), {}
    return None, {}


async def ask(client, session, tools, arm: str, q: dict, model: str) -> dict:
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=16000,
        system=ARMS[arm]["system"],
        messages=[{"role": "user", "content": q["question"]}],
        tools=[async_mcp_tool(t, session) for t in tools],
        output_config={"effort": "medium"},
        max_iterations=12,
        **extra,
    )
    input_tokens = output_tokens = tool_calls = 0
    message = None
    async for message in runner:
        input_tokens += message.usage.input_tokens + (message.usage.cache_read_input_tokens or 0)
        output_tokens += message.usage.output_tokens
        tool_calls += sum(1 for b in message.content if b.type == "tool_use")

    text = "\n".join(b.text for b in message.content if b.type == "text") if message else ""
    got = parse_answer(text)
    point, judge = await makes_point(client, q, text)
    return {
        "id": q["id"],
        "arm": arm,
        "model": model,
        "expected": q["expected"],
        "got": got,
        "correct": is_correct(q, got),
        "makes_point": point,
        "stop_reason": message.stop_reason if message else None,
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "answer": text,
        **judge,
    }


async def run(args, questions) -> list[dict]:
    client = anthropic.AsyncAnthropic()
    limit = asyncio.Semaphore(args.concurrency)

    async with streamable_http_client(args.mcp_url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            all_tools = (await session.list_tools()).tools

            async def one(arm, q, repeat):
                async with limit:
                    tools = [t for t in all_tools if t.name in ARMS[arm]["tools"]]
                    try:
                        result = await ask(client, session, tools, arm, q, args.model)
                    except anthropic.APIError as e:
                        result = {"id": q["id"], "arm": arm, "model": args.model, "expected": q["expected"],
                                  "got": None, "correct": False, "makes_point": None, "error": str(e)}
                    result["repeat"] = repeat
                    point = {True: "point made", False: "POINT MISSED", None: ""}[result["makes_point"]]
                    mark = "ok " if result["correct"] else "BAD"
                    print(f"{mark} {arm:15} {q['id']:32} expected {q['expected'][0]:.4g}, got {result['got']}  {point}")
                    return result

            jobs = [one(arm, q, r) for r in range(args.repeats) for arm in args.arms for q in questions]
            return await asyncio.gather(*jobs)


def cost(rows: list[dict]) -> float:
    total = 0.0
    for r in rows:
        price_in, price_out = PRICES.get(r["model"], (0, 0))
        total += r.get("input_tokens", 0) / 1e6 * price_in + r.get("output_tokens", 0) / 1e6 * price_out
        if usage := r.get("judge_usage"):
            judge_in, judge_out = PRICES[JUDGE_MODEL]
            total += usage["input_tokens"] / 1e6 * judge_in + usage["output_tokens"] / 1e6 * judge_out
    return total


def summarize(results: list[dict], arms: list[str]) -> str:
    lines = [
        "| Setup | Correct number | Made the point | Both | Tool calls per answer | Cost |",
        "|---|---|---|---|---|---|",
    ]
    for arm in arms:
        rows = [r for r in results if r["arm"] == arm]
        graded = [r for r in rows if r.get("makes_point") is not None]
        both = sum(r["correct"] and r["makes_point"] for r in graded)
        calls = sum(r.get("tool_calls", 0) for r in rows) / max(len(rows), 1)
        lines.append(
            f"| {arm} | {sum(r['correct'] for r in rows)}/{len(rows)} "
            f"| {sum(bool(r['makes_point']) for r in graded)}/{len(graded)} | {both}/{len(graded)} "
            f"| {calls:.1f} | ${cost(rows):.2f} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="questions.yml", help="file in evals/")
    parser.add_argument("--dry-run", action="store_true", help="print the expected answers and exit")
    parser.add_argument("--regrade", nargs="+", metavar="RESULTS_JSON", help="re-check stored answers against the current answer key")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--repeats", type=int, default=1, help="ask each question this many times")
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--mcp-url", default="http://localhost:8000/mcp")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    if args.regrade:
        for path in map(Path, args.regrade):
            data = json.loads(path.read_text())
            by_id = {q["id"]: q for q in load_questions(EVAL_DIR / data["questions"], None)}
            for r in data["results"]:
                r["expected"] = by_id[r["id"]]["expected"]
                r["correct"] = is_correct(by_id[r["id"]], r["got"])
            path.write_text(json.dumps(data, indent=1))
            print(f"{path.name}\n{summarize(data['results'], list(ARMS))}\n")
        return

    questions = load_questions(EVAL_DIR / args.questions, args.limit)
    if args.dry_run:
        for q in questions:
            print(f"{q['id']:32} {', '.join(f'{e:.6g}' for e in q['expected'])}")
        return

    results = asyncio.run(run(args, questions))
    summary = summarize(results, args.arms)
    print("\n" + summary)

    out_dir = EVAL_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}_{Path(args.questions).stem}_{args.model}"
    meta = {"model": args.model, "questions": args.questions, "repeats": args.repeats, "judge": JUDGE_MODEL}
    (out_dir / f"{name}.json").write_text(json.dumps({**meta, "results": results}, indent=1))
    print(f"\nWrote evals/results/{name}.json")


if __name__ == "__main__":
    main()
