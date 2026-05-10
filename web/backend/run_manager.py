from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from web.backend.embedded.default_config import DEFAULT_CONFIG
from web.backend.embedded.graph.trading_graph import TradingAgentsGraph

from .db import DB
from .reporting import save_report_to_disk
from .schemas import RunRequest

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}
RISK_AGENTS = ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"]
RESEARCH_AGENTS = ["Bull Researcher", "Bear Researcher", "Research Manager"]


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


def _extract_content_string(content: Any) -> str | None:
    def is_empty(v: Any) -> bool:
        return v is None or (isinstance(v, str) and not v.strip())

    if isinstance(content, str):
        return content.strip() if not is_empty(content) else None
    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", "").strip())
            elif isinstance(item, str):
                text_parts.append(item.strip())
        joined = " ".join(t for t in text_parts if t)
        return joined if joined else None
    s = str(content).strip()
    return s if s else None


def _classify_message_type(message: Any) -> tuple[str, str | None]:
    content = _extract_content_string(getattr(message, "content", None))
    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)
    if isinstance(message, ToolMessage):
        return ("Data", content)
    if isinstance(message, AIMessage):
        return ("Agent", content)
    return ("System", content)


class RunManager:
    def list_runs(self) -> list[dict[str, Any]]:
        return DB.list_runs()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return DB.get_run(run_id)

    def list_events(
        self, run_id: str, after_id: int = 0, event_types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return DB.list_events(run_id, after_id, event_types=event_types)

    def request_cancel(self, run_id: str) -> dict[str, Any] | None:
        rec = DB.get_run(run_id)
        if not rec:
            return None
        if rec["status"] in {"completed", "failed", "cancelled"}:
            return rec
        DB.update_run(run_id, cancel_requested=1, status="cancelled", ended_at=_now())
        self._emit(run_id, "status", {"status": "cancelled", "cancel_requested": True})
        return DB.get_run(run_id)

    def delete_run(self, run_id: str) -> tuple[bool, str | None]:
        rec = DB.get_run(run_id)
        if not rec:
            return False, "run not found"
        if rec["status"] in {"queued"}:
            return False, "cannot delete a queued/running run"
        if rec["status"] == "running" and not rec.get("cancel_requested"):
            return False, "cannot delete a queued/running run"
        deleted = DB.delete_run(run_id)
        if not deleted:
            return False, "run not found"
        return True, None

    def create_run(self, req: RunRequest) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:12]
        row = {
            "run_id": run_id,
            "ticker": req.ticker.strip().upper(),
            "analysis_date": req.analysis_date.isoformat(),
            "status": "queued",
            "progress": 0,
            "cancel_requested": False,
            "created_at": _now(),
        }
        DB.create_run(row)
        DB.add_event(run_id, _now(), "status", {"status": "queued"})

        worker = threading.Thread(target=self._execute_run, args=(run_id, req), daemon=True)
        worker.start()
        return DB.get_run(run_id) or row

    def _emit(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if not DB.get_run(run_id):
            return
        DB.add_event(run_id, _now(), event_type, payload)

    def _execute_run(self, run_id: str, req: RunRequest) -> None:
        DB.update_run(run_id, status="running", started_at=_now(), progress=1)
        self._emit(run_id, "status", {"status": "running", "progress": 1})

        # Run may be cancelled/deleted right after creation.
        current = DB.get_run(run_id)
        if not current:
            return
        if current.get("cancel_requested") or current.get("status") == "cancelled":
            DB.update_run(run_id, status="cancelled", ended_at=_now())
            self._emit(run_id, "status", {"status": "cancelled"})
            return

        try:
            config = DEFAULT_CONFIG.copy()
            config["max_debate_rounds"] = req.research_depth
            config["max_risk_discuss_rounds"] = req.research_depth
            config["quick_think_llm"] = req.shallow_thinker
            config["deep_think_llm"] = req.deep_thinker
            config["backend_url"] = req.backend_url
            config["llm_provider"] = req.llm_provider.lower()
            config["google_thinking_level"] = req.google_thinking_level
            config["openai_reasoning_effort"] = req.openai_reasoning_effort
            config["anthropic_effort"] = req.anthropic_effort
            config["output_language"] = req.output_language
            config["checkpoint_enabled"] = req.checkpoint

            selected = [a for a in ANALYST_ORDER if a in req.analysts]
            agent_status: dict[str, str] = {}
            for k in selected:
                agent_status[ANALYST_AGENT_NAMES[k]] = "pending"
            for a in RESEARCH_AGENTS + ["Trader"] + RISK_AGENTS:
                agent_status[a] = "pending"

            report_sections: dict[str, str] = {}
            processed_ids: set[str] = set()

            graph = TradingAgentsGraph(selected_analysts=req.analysts, config=config, debug=True)
            init_state = graph.propagator.create_initial_state(req.ticker.strip().upper(), req.analysis_date.isoformat())
            args = graph.propagator.get_graph_args(callbacks=[])

            self._emit(run_id, "meta", {"ticker": req.ticker.strip().upper(), "analysis_date": req.analysis_date.isoformat()})
            trace = []
            for chunk in graph.graph.stream(init_state, **args):
                current = DB.get_run(run_id)
                if not current:
                    return
                if current.get("cancel_requested") or current.get("status") == "cancelled":
                    DB.update_run(run_id, status="cancelled", ended_at=_now())
                    self._emit(run_id, "status", {"status": "cancelled"})
                    return

                for message in chunk.get("messages", []):
                    msg_id = getattr(message, "id", None)
                    if msg_id is not None:
                        if msg_id in processed_ids:
                            continue
                        processed_ids.add(msg_id)

                    msg_type, content = _classify_message_type(message)
                    if content and content.strip():
                        self._emit(run_id, "message", {"type": msg_type, "content": content})

                    if hasattr(message, "tool_calls") and message.tool_calls:
                        for tc in message.tool_calls:
                            if isinstance(tc, dict):
                                name, targs = tc.get("name"), tc.get("args")
                            else:
                                name, targs = getattr(tc, "name", "tool"), getattr(tc, "args", {})
                            self._emit(run_id, "tool_call", {"name": name, "args": targs})

                for key in ["market_report", "sentiment_report", "news_report", "fundamentals_report", "investment_plan", "trader_investment_plan", "final_trade_decision"]:
                    if chunk.get(key):
                        report_sections[key] = chunk[key]
                        self._emit(run_id, "report_section", {"section": key, "content": chunk[key]})

                if chunk.get("investment_debate_state"):
                    deb = chunk["investment_debate_state"]
                    if deb.get("bull_history"):
                        report_sections["investment_plan"] = f"### Bull Researcher Analysis\n{deb.get('bull_history','')}"
                    if deb.get("bear_history"):
                        report_sections["investment_plan"] = f"### Bear Researcher Analysis\n{deb.get('bear_history','')}"
                    if deb.get("judge_decision"):
                        report_sections["investment_plan"] = f"### Research Manager Decision\n{deb.get('judge_decision','')}"
                        for a in RESEARCH_AGENTS:
                            agent_status[a] = "completed"
                        agent_status["Trader"] = "in_progress"

                if chunk.get("risk_debate_state"):
                    risk = chunk["risk_debate_state"]
                    if risk.get("aggressive_history"):
                        agent_status["Aggressive Analyst"] = "in_progress"
                    if risk.get("conservative_history"):
                        agent_status["Conservative Analyst"] = "in_progress"
                    if risk.get("neutral_history"):
                        agent_status["Neutral Analyst"] = "in_progress"
                    if risk.get("judge_decision"):
                        for a in RISK_AGENTS:
                            agent_status[a] = "completed"

                found_active = False
                for k in ANALYST_ORDER:
                    if k not in selected:
                        continue
                    an = ANALYST_AGENT_NAMES[k]
                    rep_key = ANALYST_REPORT_MAP[k]
                    has_report = bool(report_sections.get(rep_key) or chunk.get(rep_key))
                    if has_report:
                        agent_status[an] = "completed"
                    elif not found_active:
                        agent_status[an] = "in_progress"
                        found_active = True
                    else:
                        agent_status[an] = "pending"

                if not found_active and selected and agent_status.get("Bull Researcher") == "pending":
                    agent_status["Bull Researcher"] = "in_progress"

                self._emit(run_id, "agent_status", {"statuses": agent_status})
                progress = self._estimate_progress(agent_status, report_sections)
                DB.update_run(run_id, progress=progress)
                self._emit(run_id, "progress", {"value": progress})
                trace.append(chunk)

            final_state = trace[-1] if trace else {}
            current = DB.get_run(run_id)
            if not current:
                return
            if current.get("cancel_requested") or current.get("status") == "cancelled":
                DB.update_run(run_id, status="cancelled", ended_at=_now())
                self._emit(run_id, "status", {"status": "cancelled"})
                return
            graph.process_signal(final_state.get("final_trade_decision", ""))

            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_root = Path("reports") / f"{req.ticker.strip().upper()}_{timestamp}"
            save_report_to_disk(final_state, req.ticker.strip().upper(), report_root)

            report_files = sorted(str(p.relative_to(report_root)) for p in report_root.rglob("*.md"))
            # Ensure UI receives a final, fully-completed snapshot for every tracked agent.
            for agent in list(agent_status.keys()):
                agent_status[agent] = "completed"
            self._emit(run_id, "agent_status", {"statuses": agent_status})

            DB.update_run(
                run_id,
                status="completed",
                ended_at=_now(),
                progress=100,
                report_dir=str(report_root.resolve()),
                report_files_json=json.dumps(report_files, ensure_ascii=False),
                final_state_json=json.dumps(final_state, ensure_ascii=False, default=str),
            )
            self._emit(run_id, "status", {"status": "completed", "progress": 100, "report_files": report_files})
        except Exception as exc:  # pragma: no cover
            DB.update_run(run_id, status="failed", ended_at=_now(), error=str(exc))
            self._emit(run_id, "status", {"status": "failed", "error": str(exc)})

    def _estimate_progress(self, agent_status: dict[str, str], report_sections: dict[str, str]) -> int:
        total_agents = max(len(agent_status), 1)
        completed_agents = sum(1 for v in agent_status.values() if v == "completed")
        agent_score = int((completed_agents / total_agents) * 80)
        report_score = min(len(report_sections), 7) * 2
        value = min(95, agent_score + report_score)
        return max(1, value)


RUN_MANAGER = RunManager()
