"""
demo_repair_assistant.py
========================
Demonstrates the complete repair workflow system for wrench-voice.

Run this to see the 1998 Camry water pump + timing belt workflow in action,
including tool matching, step-by-step tracking, and next-step prediction.

Usage:
    python demo_repair_assistant.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wrench_voice.repair_workflow import (
    RepairWorkflowRegistry,
    WorkflowTracker,
    ToolMatcher,
)
from wrench_voice.workflow_predictor import NextStepPredictor


def print_banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def demo_camry_water_pump() -> None:
    """Walk through the 1998 Camry 5S-FE water pump + timing belt job."""

    print_banner("1998 Toyota Camry 5S-FE: Water Pump + Timing Belt")
    print("This is the user's example — fully instrumented with tools, fasteners,")
    print("safety warnings, and real-time predictions.")

    # Load workflow
    reg = RepairWorkflowRegistry()
    wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
    tracker = WorkflowTracker(wf)
    predictor = NextStepPredictor(tracker)

    print(f"\n📋 JOB OVERVIEW")
    print(f"   Title: {wf.title}")
    print(f"   Skill level: {wf.skill_level}")
    print(f"   Estimated time: {wf.estimated_total_time_min} minutes ({wf.estimated_total_time_min // 60}h {wf.estimated_total_time_min % 60}m)")
    print(f"   Total steps: {len(wf.steps)}")

    print(f"\n🛠️  REQUIRED TOOLS")
    for tool in wf.required_tools_summary:
        print(f"   • {tool}")

    print(f"\n⚠️  CRITICAL CAUTIONS")
    for c in wf.cautions:
        print(f"   ⚠️  {c}")

    print(f"\n📦 CONSUMABLES")
    for c in wf.consumables:
        print(f"   • {c}")

    # Simulate mechanic walking through steps
    print_banner("SIMULATING MECHANIC WORKFLOW")

    steps_to_demo = min(8, len(wf.steps))
    for i in range(steps_to_demo):
        step = tracker.current_step
        if not step:
            break

        print(f"\n{'─'*60}")
        print(f"STEP {step.step_number}: {step.title}")
        print(f"{'─'*60}")
        print(f"📝 {step.description}")

        # Show exact fasteners with sizes
        if step.fasteners:
            print(f"\n🔩 FASTENERS:")
            for f in step.fasteners:
                size_info = f.drive if f.drive else f.size
                print(f"   • {f.description}: {size_info} → {f.torque_str()}")
                if f.notes:
                    print(f"     Note: {f.notes}")

        # Show required tools
        if step.required_tools:
            print(f"\n🔧 TOOLS:")
            for t in step.required_tools:
                print(f"   • {t}")

        # Show safety warnings
        if step.safety_warnings:
            print(f"\n🚨 SAFETY WARNINGS:")
            for w in step.safety_warnings:
                print(f"   ⚠️  {w}")

        # Show inspection notes
        if step.inspection_notes:
            print(f"\n🔍 INSPECT:")
            for note in step.inspection_notes:
                print(f"   • {note}")

        # Predictions for NEXT steps
        predictions = predictor.predict(lookahead=3)
        critical = [p for p in predictions if p.urgency == "critical"]
        if critical:
            print(f"\n🔮 CRITICAL LOOKAHEAD:")
            for p in critical[:2]:
                print(f"   ⚠️  {p.message}")

        # Advance
        tracker.advance()

    # Final status
    print_banner("PROGRESS SUMMARY")
    summary = tracker.status_summary()
    print(f"   Progress: {summary['progress_pct']}%")
    print(f"   Time remaining: {summary['time_remaining_min']} min")
    print(f"   Flags set: {list(summary['prerequisites_met'].keys())}")
    print(f"\n   Next tools (3-step lookahead):")
    for t in summary['next_tools'][:8]:
        print(f"      • {t}")
    print(f"\n   Next fasteners (2-step lookahead):")
    for f in summary['next_fasteners'][:4]:
        print(f"      • {f['desc']}: {f['drive']} → {f['torque']}")


def demo_prediction_engine() -> None:
    """Show the prediction engine in detail."""

    print_banner("PREDICTION ENGINE DEMO")
    print("The predictor anticipates what the mechanic needs BEFORE they ask.")

    reg = RepairWorkflowRegistry()
    wf = reg.get("toyota_5sfe", "water_pump_timing_belt")
    tracker = WorkflowTracker(wf)
    predictor = NextStepPredictor(tracker)

    # Show all predictions at the start of the job
    predictions = predictor.predict()
    print(f"\n🔮 Predictions at job START (Step 1):")
    print(f"   Total predictions: {len(predictions)}")

    for p in predictions:
        icon = {"tool": "🔧", "fastener": "🔩", "warning": "🚨", "procedure": "📋", "time": "⏱️"}.get(p.category, "•")
        print(f"\n   {icon} [{p.urgency.upper()}] Step +{p.step_ahead}: {p.message}")
        if p.confidence < 1.0:
            print(f"      Confidence: {p.confidence:.0%}")


def demo_tool_matcher() -> None:
    """Show tool resolution by engine family."""

    print_banner("TOOL MATCHER DEMO")
    print("Generic tool requests resolved to exact sizes per engine family.")

    families = ["toyota_5sfe", "subaru_ej25_sohc", "honda_j_series", "ford_73_powerstroke"]
    categories = ["socket set", "torque critical", "timing belt", "coolant system"]

    for family in families:
        matcher = ToolMatcher(family)
        print(f"\n🔧 {family}:")
        for cat in categories:
            tools = matcher.resolve(cat)
            if tools and tools != [cat]:  # Only show if resolved
                print(f"   '{cat}' → {', '.join(tools[:3])}")


def demo_subaru_head_gasket() -> None:
    """Brief walkthrough of Subaru HG job to show cross-family support."""

    print_banner("BONUS: Subaru EJ25 SOHC Head Gasket")
    print("Shows the same system works across engine families.")

    reg = RepairWorkflowRegistry()
    wf = reg.get("subaru_ej25_sohc", "head_gasket")
    tracker = WorkflowTracker(wf)

    print(f"\n📋 JOB OVERVIEW")
    print(f"   Title: {wf.title}")
    print(f"   Skill level: {wf.skill_level}")
    print(f"   Steps: {len(wf.steps)}")

    print(f"\n⚠️  CRITICAL CAUTIONS")
    for c in wf.cautions:
        print(f"   ⚠️  {c}")

    # Show step 3 (head removal) with TTY bolt warning
    for _ in range(2):
        tracker.advance()
    step = tracker.current_step
    print(f"\n{'─'*60}")
    print(f"STEP {step.step_number}: {step.title}")
    print(f"{'─'*60}")
    if step.fasteners:
        print(f"🔩 FASTENERS:")
        for f in step.fasteners:
            print(f"   • {f.description}: {f.size} → {f.torque_str()}")
            if f.notes:
                print(f"     NOTE: {f.notes}")


if __name__ == "__main__":
    demo_camry_water_pump()
    demo_prediction_engine()
    demo_tool_matcher()
    demo_subaru_head_gasket()

    print_banner("DEMO COMPLETE")
    print("The system now supports:")
    print("   1. Exact tool matching per engine family")
    print("   2. Step-by-step repair tracking with state machine")
    print("   3. Real-time prediction of next tools, fasteners, and warnings")
    print("   4. Prerequisite checking (did they drain coolant?)")
    print("   5. Common mistake warnings (e.g. impact gun on crank bolt)")
    print("   6. Progress reporting with time remaining")
    print("\nNext steps:")
    print("   • Add more workflows: valve cover gasket, spark plugs, brake jobs")
    print("   • Connect to voice gateway for hands-free operation")
    print("   • Integrate with job_scheduler.py for bay assignment")
    print("   • Add photo/video hints per step for visual guidance")
