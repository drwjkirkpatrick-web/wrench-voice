"""
ollama_bridge.py
================
Local Ollama integration for wrench-voice: natural language understanding,
procedure Q&A, and voice command parsing — all offline, no API keys.

WHY:
A mechanic speaking into a headset says things like:
  "My Camry is overheating and I already checked the coolant level."
  "What size socket for the water pump bolts?"
  "Go to step 7."
  "What's the torque on the tensioner bolt?"

This bridge:
1. Parses those utterances into structured intents
2. Answers procedural questions from loaded workflow context
3. Generates concise, accurate responses using local Ollama
4. Never leaves the shop (no cloud, no subscription, no latency)

BACKEND:
- Ollama on localhost:11434 (default)
- Models: qwen2.5:3b (fast NLU), llama3.2:3b (general knowledge)
- Temperature low (0.3–0.5) for factual repair info
- System prompt tuned for mechanic context

FEATURES:
- intent_classification: "what_tool" | "what_torque" | "goto_step" | "explain_step" | "general_question" | "status_check" | "unknown"
- workflow_qa: Answers questions about current procedure using workflow context
- command_parsing: "Go to step 5" → {"action": "goto", "step": 5}
- part_lookup_nlp: "I need a thermostat for a 1998 Camry" → structured part request
- summarize_diagnosis: Converts verbose mechanic description into symptom slugs
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class NLUResult:
    """Structured result from parsing a natural language utterance."""
    intent: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    response: str = ""          # Generated response if applicable
    action: str = ""           # Structured action: goto_step | advance | back | repeat | unknown
    action_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowQAContext:
    """Context for answering questions about a loaded workflow."""
    engine_slug: str = ""
    symptom: str = ""
    current_step: int = 0
    total_steps: int = 0
    step_title: str = ""
    step_description: str = ""
    fasteners: list[dict[str, Any]] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    progress_pct: float = 0.0

    def to_prompt(self) -> str:
        """Serialize to a concise prompt snippet for the LLM."""
        lines = [
            f"Current job: {self.engine_slug} — {self.symptom}",
            f"Step {self.current_step} of {self.total_steps} ({self.progress_pct:.0f}% complete)",
            f"Title: {self.step_title}",
            f"Description: {self.step_description}",
        ]
        if self.tools:
            lines.append(f"Tools: {', '.join(self.tools)}")
        if self.fasteners:
            lines.append(f"Fasteners: {len(self.fasteners)} items")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)} items")
        return "\n".join(lines)


class OllamaBridge:
    """
    Local Ollama client for wrench-voice voice and text interfaces.

    Usage:
        bridge = OllamaBridge(model="qwen2.5:3b")
        result = bridge.classify_intent("What's the torque on the water pump bolts?")
        print(result.intent)  # "what_torque"

        # With workflow context
        ctx = WorkflowQAContext(engine_slug="toyota_5sfe", current_step=7, ...)
        answer = bridge.answer_procedure_question("Do I need to replace the tensioner?", ctx)
        print(answer.response)
    """

    DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    DEFAULT_MODEL = os.environ.get("WRENCH_OLLAMA_MODEL", "qwen2.5-cpu:latest")
    FALLBACK_MODEL = "qwen2.5-cpu:latest"

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float = 0.3,
        timeout: float = 10.0,
        mock_mode: bool = False,
    ) -> None:
        self.model = model or self.DEFAULT_MODEL
        self.host = (host or self.DEFAULT_HOST).rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.mock_mode = mock_mode
        self._available = False
        self._available_models: list[str] = []

    # ─── Connection ──────────────────────────────────────────────────────────

    def check_available(self) -> bool:
        """Ping Ollama server and list available models."""
        if self.mock_mode:
            self._available = True
            return True
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                self._available_models = [m["name"] for m in data.get("models", [])]
                self._available = self.model in self._available_models or not self._available_models
                return self._available
        except Exception:
            self._available = False
            return False

    def is_available(self) -> bool:
        return self._available or self.mock_mode

    # ─── Low-level Chat ────────────────────────────────────────────────────────

    def chat(self, user_message: str, system: str = "", stream: bool = False) -> str:
        """Send a message to Ollama and return the response text."""
        if self.mock_mode:
            return self._mock_response(user_message, system)

        try:
            import urllib.request
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                "stream": stream,
                "options": {"temperature": self.temperature, "num_predict": 512},
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.host}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                full_text = ""
                for line in resp.read().decode().strip().split("\n"):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})
                        if msg.get("role") == "assistant" and msg.get("content"):
                            full_text += msg["content"]
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
                return full_text.strip()
        except Exception as e:
            return f"[OLLAMA ERROR: {e}]"

    def generate(self, prompt: str, system: str = "") -> str:
        """Direct /api/generate call — simpler for single-turn tasks."""
        if self.mock_mode:
            return self._mock_response(prompt, system)

        try:
            import urllib.request
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": self.temperature, "num_predict": 512},
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode())
                return result.get("response", "").strip()
        except Exception as e:
            return f"[OLLAMA ERROR: {e}]"

    # ─── Intent Classification ───────────────────────────────────────────────

    def classify_intent(self, utterance: str) -> NLUResult:
        """
        Classify a mechanic's voice/text utterance into an intent.
        Intents: what_tool, what_torque, goto_step, advance, back, explain_step,
                 status_check, general_question, unknown
        """
        system = (
            "You are a mechanic assistant intent classifier. "
            "Classify the user's utterance into EXACTLY one of these intents: "
            "what_tool, what_torque, what_size, goto_step, advance, back, repeat, "
            "explain_step, status_check, part_lookup, general_question, unknown. "
            "Respond with ONLY a JSON object: {\"intent\": \"...\", \"confidence\": 0.95, "
            "\"entities\": {...}, \"action\": \"...\", \"action_params\": {...}}. "
            "Confidence is 0.0–1.0. Entities may include: tool_name, step_number, part_name, "
            "torque_component, engine."
        )
        raw = self.generate(utterance, system=system)
        return self._parse_nlu_json(raw, utterance)

    # ─── Procedure Q&A ───────────────────────────────────────────────────────

    def answer_procedure_question(self, question: str, ctx: WorkflowQAContext) -> NLUResult:
        """
        Answer a question about the current repair procedure.
        Uses workflow context + local knowledge — no web search.
        """
        system = (
            "You are an expert mechanic assistant. Answer questions about the current repair "
            "procedure concisely and accurately. NEVER make up torque values or tool sizes. "
            "If the answer is in the provided context, use it. If not, say you don't know. "
            "Keep responses under 3 sentences. Use imperial units (ft-lb, inches) unless metric is standard."
        )
        prompt = f"Context:\n{ctx.to_prompt()}\n\nQuestion: {question}\n\nAnswer:"
        answer_text = self.generate(prompt, system=system)
        return NLUResult(
            intent="general_question",
            confidence=0.90,
            raw_text=question,
            response=answer_text,
        )

    # ─── Command Parsing ─────────────────────────────────────────────────────

    def parse_command(self, utterance: str) -> NLUResult:
        """
        Parse a direct voice command into structured action.
        Examples:
            "Go to step 5" → action=goto, step=5
            "Next step" → action=advance
            "Repeat that" → action=repeat
            "What size is the crank bolt?" → action=what_size, component="crank bolt"
        """
        system = (
            "You parse mechanic voice commands. Respond ONLY with JSON: "
            "{\"intent\": \"...\", \"action\": \"...\", \"action_params\": {...}, \"confidence\": 0.95}. "
            "Actions: goto, advance, back, repeat, what_size, what_torque, what_tool, status, unknown. "
            "action_params depends on action: goto uses step, what_size uses component."
        )
        raw = self.generate(utterance, system=system)
        return self._parse_nlu_json(raw, utterance)

    # ─── Diagnosis Summarization ─────────────────────────────────────────────

    def summarize_symptoms(self, description: str) -> NLUResult:
        """
        Convert a verbose mechanic/customer description into structured symptom data.
        Example: "It's making a knocking noise when I accelerate, and the oil light flickers"
        → {"symptoms": ["knocking_under_load", "oil_pressure_light"], ...}
        """
        system = (
            "You extract symptoms from mechanic descriptions. "
            "Respond ONLY with JSON: {\"symptoms\": [\"slug1\", \"slug2\"], "
            "\"make\": \"...\", \"model\": \"...\", \"year\": 1998, \"engine\": \"...\", "
            "\"urgency\": \"normal|urgent|critical\", \"confidence\": 0.85}. "
            "Use lowercase snake_case symptom slugs. If info is missing, use null."
        )
        raw = self.generate(description, system=system)
        result = self._parse_nlu_json(raw, description)
        if result.intent == "unknown":
            # Fallback: return the raw response as a general summary
            return NLUResult(
                intent="symptom_summary",
                confidence=0.70,
                raw_text=description,
                response=raw,
            )
        return result

    # ─── Voice Gateway Integration ───────────────────────────────────────────

    def transcribe_to_intent(self, text: str, ctx: WorkflowQAContext | None = None) -> NLUResult:
        """
        Full pipeline: transcribed text → intent → action → response.
        Used by voice gateway after STT produces text.
        """
        # First try direct command parsing (fast, deterministic)
        cmd = self.parse_command(text)
        if cmd.confidence >= 0.85 and cmd.action not in ("", "unknown"):
            return cmd

        # Then try classification with workflow context
        if ctx:
            return self.answer_procedure_question(text, ctx)

        # Fallback: general intent classification
        return self.classify_intent(text)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _parse_nlu_json(self, raw: str, original: str) -> NLUResult:
        """Parse JSON from LLM response, with fallback on parse failure."""
        # Try to extract JSON from markdown code blocks or raw text
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()

        # Find first JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            data = json.loads(text)
            return NLUResult(
                intent=data.get("intent", "unknown"),
                confidence=float(data.get("confidence", 0.5)),
                entities=data.get("entities", {}),
                raw_text=original,
                action=data.get("action", ""),
                action_params=data.get("action_params", {}),
            )
        except json.JSONDecodeError:
            # Fallback: use raw text as response
            return NLUResult(
                intent="unknown",
                confidence=0.3,
                raw_text=original,
                response=raw,
            )

    def _mock_response(self, prompt: str, system: str) -> str:
        """Mock mode: deterministic responses for testing without Ollama."""
        p = prompt.lower()
        if "intent" in system.lower() or "classify" in system.lower():
            if "torque" in p:
                return '{"intent": "what_torque", "confidence": 0.95, "entities": {"component": "tensioner bolt"}, "action": "what_torque", "action_params": {}}'
            if "step" in p and any(w in p for w in ["go to", "jump", "goto"]):
                num = re.search(r'(\d+)', p)
                step = int(num.group(1)) if num else 1
                return f'{{"intent": "goto_step", "confidence": 0.95, "action": "goto", "action_params": {{"step": {step}}}}}'
            if "next" in p:
                return '{"intent": "advance", "confidence": 0.95, "action": "advance", "action_params": {}}'
            if "size" in p or "socket" in p:
                return '{"intent": "what_size", "confidence": 0.90, "action": "what_size", "action_params": {"component": "water pump bolt"}}'
            return '{"intent": "general_question", "confidence": 0.70, "action": "unknown", "action_params": {}}'

        if "parse" in system.lower() or "command" in system.lower():
            if "go to step" in p:
                num = re.search(r'(\d+)', p)
                step = int(num.group(1)) if num else 1
                return f'{{"intent": "goto_step", "action": "goto", "action_params": {{"step": {step}}}, "confidence": 0.95}}'
            if "next" in p:
                return '{"intent": "advance", "action": "advance", "action_params": {}, "confidence": 0.95}}'
            return '{"intent": "unknown", "action": "unknown", "action_params": {}, "confidence": 0.50}}'

        if "symptom" in system.lower():
            return '{"symptoms": ["knocking_under_load", "oil_pressure_light"], "make": "Toyota", "model": "Camry", "year": 1998, "engine": "5S-FE", "urgency": "urgent", "confidence": 0.85}'

        # Default mock QA response
        return "The water pump bolts are 10mm socket and torque to 14 foot-pounds in a cross pattern."


# ─── Convenience Functions ─────────────────────────────────────────────────────

def quick_intent(text: str, model: str | None = None) -> NLUResult:
    """One-shot intent classification."""
    bridge = OllamaBridge(model=model, mock_mode=not OllamaBridge().check_available())
    return bridge.classify_intent(text)


def quick_qa(question: str, ctx: WorkflowQAContext, model: str | None = None) -> str:
    """One-shot procedure Q&A."""
    bridge = OllamaBridge(model=model, mock_mode=not OllamaBridge().check_available())
    result = bridge.answer_procedure_question(question, ctx)
    return result.response
