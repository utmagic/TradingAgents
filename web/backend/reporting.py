from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict

from web.backend.embedded.dataflows.config import get_config


def save_report_to_disk(final_state: Dict[str, Any], ticker: str, save_path: Path) -> Path:
    """Save complete analysis report to disk with organized subfolders."""
    save_path.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []
    lang = get_config().get("output_language", "English").strip().lower()
    is_ko = lang in {"korean", "ko", "kr", "한국어"}

    labels = {
        "header": "트레이딩 분석 리포트" if is_ko else "Trading Analysis Report",
        "generated": "생성시각" if is_ko else "Generated",
        "sec_1": "I. 애널리스트 팀 리포트" if is_ko else "I. Analyst Team Reports",
        "sec_2": "II. 리서치 팀 판단" if is_ko else "II. Research Team Decision",
        "sec_3": "III. 트레이딩 팀 계획" if is_ko else "III. Trading Team Plan",
        "sec_4": "IV. 리스크 관리 팀 판단" if is_ko else "IV. Risk Management Team Decision",
        "sec_5": "V. 포트폴리오 매니저 최종 판단" if is_ko else "V. Portfolio Manager Decision",
        "market_analyst": "시장 애널리스트" if is_ko else "Market Analyst",
        "social_analyst": "소셜 애널리스트" if is_ko else "Social Analyst",
        "news_analyst": "뉴스 애널리스트" if is_ko else "News Analyst",
        "fund_analyst": "펀더멘털 애널리스트" if is_ko else "Fundamentals Analyst",
        "bull": "강세 리서처" if is_ko else "Bull Researcher",
        "bear": "약세 리서처" if is_ko else "Bear Researcher",
        "research_manager": "리서치 매니저" if is_ko else "Research Manager",
        "trader": "트레이더" if is_ko else "Trader",
        "aggressive": "공격적 리스크 애널리스트" if is_ko else "Aggressive Analyst",
        "conservative": "보수적 리스크 애널리스트" if is_ko else "Conservative Analyst",
        "neutral": "중립 리스크 애널리스트" if is_ko else "Neutral Analyst",
        "portfolio_manager": "포트폴리오 매니저" if is_ko else "Portfolio Manager",
    }

    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
        analyst_parts.append((labels["market_analyst"], final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(final_state["sentiment_report"], encoding="utf-8")
        analyst_parts.append((labels["social_analyst"], final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
        analyst_parts.append((labels["news_analyst"], final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(final_state["fundamentals_report"], encoding="utf-8")
        analyst_parts.append((labels["fund_analyst"], final_state["fundamentals_report"]))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## {labels['sec_1']}\n\n{content}")

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
            research_parts.append((labels["bull"], debate["bull_history"]))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
            research_parts.append((labels["bear"], debate["bear_history"]))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")
            research_parts.append((labels["research_manager"], debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## {labels['sec_2']}\n\n{content}")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(final_state["trader_investment_plan"], encoding="utf-8")
        sections.append(f"## {labels['sec_3']}\n\n### {labels['trader']}\n{final_state['trader_investment_plan']}")

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(risk["aggressive_history"], encoding="utf-8")
            risk_parts.append((labels["aggressive"], risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(risk["conservative_history"], encoding="utf-8")
            risk_parts.append((labels["conservative"], risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
            risk_parts.append((labels["neutral"], risk["neutral_history"]))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## {labels['sec_4']}\n\n{content}")

        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")
            sections.append(f"## {labels['sec_5']}\n\n### {labels['portfolio_manager']}\n{risk['judge_decision']}")

    header = (
        f"# {labels['header']}: {ticker}\n\n"
        f"{labels['generated']}: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    report_file = save_path / "complete_report.md"
    report_file.write_text(header + "\n\n".join(sections), encoding="utf-8")
    return report_file
