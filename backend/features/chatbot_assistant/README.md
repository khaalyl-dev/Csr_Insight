# chatbot_assistant

CSR chatbot assistant (local Ollama).

---

## Files

| File | Purpose |
|------|---------|
| **chatbot_routes.py** | Blueprint `/api/chatbot`. `POST /chat` — builds a permission/site-aware data snapshot, sends it as Ollama `system` text with the user `prompt`. |
| **chatbot_focus.py** | Infers which topics the user asked about; avoids loading unrelated DB slices. |
| **chatbot_context.py** | Builds a **small** USER_DATA block (same visibility as the API) — plans / activities / etc. only when relevant. |
| **__init__.py** | Exports `chatbot_bp`. |
