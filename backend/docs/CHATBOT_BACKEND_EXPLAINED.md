# Chatbot Assistant Backend - Explication complete

Ce document explique le fonctionnement du backend du chatbot dans ce projet CSR Insight: architecture, flux d'execution, RAG, securite, exemples, et fichiers importants.

---

## 1) Vue d'ensemble

Le chatbot repose sur un flux hybride:

- **Donnees live SQL** (plans, activites, documents...) selon les permissions de l'utilisateur.
- **RAG documentaire local** (ChromaDB + corpus Markdown).
- **Generation locale** via **Ollama** (`/api/generate`), sans cloud obligatoire.

En pratique, le backend construit un `system prompt` compose de:

1. instructions systeme du chatbot,
2. bloc RAG recupere (si active),
3. snapshot metier `USER_DATA` filtre par role/site.

Puis il envoie ce contexte avec le prompt utilisateur a Ollama.

---

## 2) Endpoint principal

Le point d'entree est:

- `POST /api/chatbot/chat`
- Fichier: `backend/features/chatbot_assistant/chatbot_routes.py`

Etapes:

1. Verification JWT (`@token_required`)
2. Lecture du `prompt`
3. Selection du modele (`OLLAMA_MODEL` ou override)
4. Construction du contexte metier (`build_chatbot_system_context`)
5. Recuperation RAG (`query_rag_block`) si active
6. Enrichissement chiffrable (`build_chatbot_prompt_enrichment`)
7. Appel Ollama local (`_ollama_chat`)
8. Retour JSON `{ model, response }`

---

## 3) RAG: ou et comment il est utilise

### 3.1 Retrieval runtime

Fichier: `backend/features/chatbot_assistant/rag_store.py`

- Lit la collection Chroma `csr_insight_docs`
- Fait `coll.query(query_texts=[prompt], n_results=top_k, where=audience)`
- Construit un bloc texte `KNOWLEDGE_BASE` injecte dans le `system prompt`
- Si erreur / index absent / RAG desactive: retourne chaine vide (fallback propre)

### 3.2 Ingestion corpus

Fichier: `backend/features/chatbot_assistant/rag_ingest.py`

- Source: `backend/rag_corpus/*.md`
- Parse frontmatter `audience: all|corporate|site`
- Chunking (`RAG_CHUNK_MAX_CHARS`, defaut 600)
- Ecriture dans Chroma persistent (`RAG_CHROMA_PATH`)

Commande:

```bash
python -m features.chatbot_assistant.rag_ingest
```

---

## 4) Contexte metier dynamique (SQL + permissions)

Fichier cle: `backend/features/chatbot_assistant/chatbot_context.py`

Points importants:

- Le modele **n'execute pas SQL directement**.
- Le backend calcule les chiffres avec SQLAlchemy.
- Les donnees sont limitees par:
  - role (`CORPORATE`, `SITE`)
  - scope site (`data_scope_site_ids`)
  - permissions (`has_permission`)
  - regles de visibilite plans (`csr_plans_visible_query`)

Le contexte `USER_DATA` inclut seulement les sections utiles (plans, activites, realized, documents, routes...), selon la question.

---

## 5) Compression de contexte (focus intelligent)

Fichier: `backend/features/chatbot_assistant/chatbot_focus.py`

Objectif: reduire les tokens et accelerer la reponse.

Le backend detecte l'intention:

- question de quantite -> charge aggregates
- question navigation -> charge routes
- question conceptuelle -> evite de charger des chiffres inutiles

Exemple:

- "Combien de plans?" -> `plan_totals=True`
- "Ou trouver documents?" -> `nav_routes=True`, pas d'aggregats lourds

---

## 6) Enrichissement anti-derive numerique

Toujours dans `chatbot_context.py`, fonction:

- `build_chatbot_prompt_enrichment(...)`

Elle prepend une ligne courte au prompt utilisateur avec des paires `key=value` exactes (totaux et statuts).

But:

- forcer les petits modeles locaux (ex: `phi3:mini`) a garder les bons chiffres,
- eviter les reponses vagues ou inventees.

Ensuite, les instructions systeme imposent de **reformuler** ces chiffres proprement dans la reponse (sans recoller brut les tokens).

---

## 7) Securite backend

### 7.1 Endpoint protege

- `@token_required` sur `/api/chatbot/chat`

### 7.2 Ollama local/prive seulement

Dans `chatbot_routes.py`, `_is_allowed_ollama_host(...)` autorise:

- `localhost`, `127.0.0.1`
- LAN prive (`10.x`, `192.168.x`, `172.16-31.x`)

Interdit les endpoints publics externes non approuves.

### 7.3 Scope des donnees

Toutes les agregations respectent les permissions et le scope site de l'utilisateur.

---

## 8) Configuration (.env / config.py)

Fichiers:

- `backend/config.py`
- `backend/.env.example`

Variables importantes:

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_NUM_PREDICT`
- `OLLAMA_NUM_CTX` (optionnel)
- `OLLAMA_TEMPERATURE`
- `RAG_ENABLED`
- `RAG_TOP_K`
- `RAG_CHROMA_PATH`
- `RAG_CORPUS_PATH`
- `RAG_CHUNK_MAX_CHARS` (utilisee a l'ingestion)

---

## 9) Flux complet (resume)

```text
Frontend widget -> POST /api/chatbot/chat
    -> token_required (user_id, role)
    -> infer_chatbot_focus(prompt)
    -> build_chatbot_system_context(...) [SQL + permissions + scope]
    -> query_rag_block(...) [Chroma retrieval, role-aware audience]
    -> build_chatbot_prompt_enrichment(...) [exact metrics]
    -> _ollama_chat(...) [local ollama /api/generate]
    -> response JSON au frontend
```

---

## 10) Exemples concrets

### Exemple A - Quantitatif site

Question: "Combien de plans dans Serbia ?"

Backend:

- tente de resoudre le site cible,
- calcule totals + breakdown statuts dans le scope autorise,
- renvoie une reponse basee sur ces chiffres exacts.

### Exemple B - Navigation

Question: "Ou je trouve les documents ?"

Backend:

- charge surtout les routes/navigation,
- evite les gros agregats inutiles.

### Exemple C - Question fonctionnelle

Question: "Comment marche la validation des plans ?"

Backend:

- s'appuie sur le contexte metier + eventuel bloc RAG,
- explique le workflow sans inventer de donnees.

---

## 11) Fichiers backend a connaitre

- `backend/features/chatbot_assistant/chatbot_routes.py`
- `backend/features/chatbot_assistant/chatbot_context.py`
- `backend/features/chatbot_assistant/chatbot_focus.py`
- `backend/features/chatbot_assistant/rag_store.py`
- `backend/features/chatbot_assistant/rag_ingest.py`
- `backend/features/chatbot_assistant/README.md`
- `backend/docs/CHATBOT_RAG_ARCHITECTURE.md`
- `backend/rag_corpus/*.md`
- `backend/config.py`
- `backend/.env.example`
- `backend/app.py` (enregistrement blueprint `chatbot_bp`)

---

## 12) Checklist rapide de verification

1. `ollama serve` actif
2. modele present (`ollama list`, ex: `phi3:mini`)
3. `RAG_ENABLED=true` si RAG voulu
4. index Chroma cree (`python -m features.chatbot_assistant.rag_ingest`)
5. backend demarre, endpoint `/api/chatbot/chat` accessible
6. utilisateur authentifie (JWT valide)

---

## 13) Limites actuelles et ameliorations possibles

- Les reponses dependent de la qualite du corpus `rag_corpus`.
- Sans bons chunks/docs, le RAG apporte peu.
- Une evolution naturelle: endpoint de diagnostic RAG (top chunks retournes) pour debug.
- Une autre evolution: tests automatiques de prompts plus stricts sur les chiffres.

---

Ce fichier est concu pour servir de base technique dans un rapport PFE et pour l'onboarding d'un nouveau developpeur backend.
