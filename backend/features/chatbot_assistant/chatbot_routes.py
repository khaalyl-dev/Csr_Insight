"""
Chatbot assistant endpoints (local Ollama only).
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib import error
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen as urlopen_http

from flask import Blueprint, current_app, jsonify, request

from core import token_required

from .chatbot_context import (
    CHATBOT_SYSTEM_INSTRUCTIONS,
    build_chatbot_prompt_enrichment,
    build_chatbot_system_context,
)
from .rag_store import query_rag_block

logger = logging.getLogger(__name__)

bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


def _is_allowed_ollama_host(url: str) -> bool:
    """
    Allow only local/private network hosts to avoid sending prompts to public endpoints.
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1"}:
            return True
        # Private IPv4 ranges
        if host.startswith("10.") or host.startswith("192.168."):
            return True
        if host.startswith("172."):
            parts = host.split(".")
            if len(parts) >= 2:
                try:
                    second = int(parts[1])
                    return 16 <= second <= 31
                except ValueError:
                    return False
        return False
    except Exception:
        return False


def _ollama_chat(*, prompt: str, model: str, base_url: str, system: Optional[str] = None) -> str:
    base_url = base_url.strip().rstrip("/")
    if not _is_allowed_ollama_host(base_url):
        raise ValueError("OLLAMA_BASE_URL must be localhost or private network host.")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system and str(system).strip():
        payload["system"] = str(system).strip()
    opts: dict = {}
    np = current_app.config.get("OLLAMA_NUM_PREDICT")
    if np is not None:
        try:
            opts["num_predict"] = max(64, int(np))
        except (TypeError, ValueError):
            pass
    nc = current_app.config.get("OLLAMA_NUM_CTX")
    if nc is not None:
        try:
            opts["num_ctx"] = max(512, int(nc))
        except (TypeError, ValueError):
            pass
    temp = current_app.config.get("OLLAMA_TEMPERATURE")
    if temp is not None:
        try:
            t = float(temp)
            if 0.0 <= t <= 2.0:
                opts["temperature"] = t
        except (TypeError, ValueError):
            pass
    if opts:
        payload["options"] = opts
    try:
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Could not serialize chat request: {e}") from e
    req = URLRequest(
        url=f"{base_url}/api/generate",
        data=body_bytes,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen_http(req, timeout=120) as res:
            body = res.read().decode("utf-8", errors="replace")
    except error.HTTPError as e:
        detail = ""
        try:
            if e.fp:
                detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.warning("Ollama HTTP %s: %s", e.code, (detail or str(e.reason))[:2000])
        msg = _ollama_error_message_from_body(detail) or detail or str(e.reason) or "Ollama request failed"
        raise ValueError(msg) from e
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Ollama returned non-JSON body (first 500 chars): %s", body[:500])
        raise ValueError("Ollama returned an invalid response. Check that `ollama serve` is running and the model exists.") from None
    err = parsed.get("error")
    if err:
        raise ValueError(str(err))
    return str(parsed.get("response") or "").strip()


def _ollama_error_message_from_body(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return str(data.get("error") or data.get("message") or "") or None
    except json.JSONDecodeError:
        return None
    return None


@bp.post("/chat")
@token_required
def chat():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"message": "prompt is required"}), 400

    default_model = str(current_app.config.get("OLLAMA_MODEL") or "phi3:mini").strip()
    model = str(data.get("model") or default_model).strip()
    if not model:
        return jsonify({"message": "model is required"}), 400

    base_url = str(current_app.config.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
    try:
        try:
            data_snapshot = build_chatbot_system_context(request.user_id, request.role, prompt)
        except Exception:
            logger.exception("chatbot context build failed — using minimal snapshot")
            data_snapshot = (
                "### USER_DATA\n"
                "(Live data snapshot could not be loaded. You may still explain CSR Insight using "
                "the navigation routes: /dashboard, /csr-plans, /planned-activities, /realized-csr, /documents.)\n"
            )
        rag_block = query_rag_block(
            prompt,
            (request.role or ""),
            chroma_path=str(current_app.config.get("RAG_CHROMA_PATH") or ""),
            top_k=int(current_app.config.get("RAG_TOP_K") or 4),
            enabled=bool(current_app.config.get("RAG_ENABLED")),
        )
        system_parts = [CHATBOT_SYSTEM_INSTRUCTIONS]
        if rag_block:
            system_parts.append(rag_block)
        system_parts.append(data_snapshot)
        system = "\n\n".join(system_parts)
        enrich = ""
        try:
            enrich = build_chatbot_prompt_enrichment(request.user_id, request.role, prompt)
        except Exception:
            logger.warning("chatbot prompt enrichment failed", exc_info=True)
        user_prompt = f"{enrich}\n\n{prompt}" if enrich else prompt
        answer = _ollama_chat(prompt=user_prompt, model=model, base_url=base_url, system=system)
        return jsonify({"model": model, "response": answer}), 200
    except ValueError as e:
        msg = str(e)
        if "OLLAMA_BASE_URL must be" in msg:
            return jsonify({"message": msg}), 400
        return jsonify({"message": msg}), 502
    except error.URLError as e:
        logger.warning("Ollama unreachable: %s", e.reason)
        return jsonify({"message": "Cannot reach local Ollama. Ensure `ollama serve` is running."}), 502
    except Exception:
        logger.exception("chatbot chat failed")
        return jsonify({"message": "Chatbot request failed"}), 500
