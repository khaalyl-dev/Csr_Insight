# Chatbot — exemples de questions pour tests manuels

Utilisez ces phrases dans le widget (ou `POST /api/chatbot/chat`) pour vérifier le contexte **USER_DATA**, la navigation et le ton court. Les réponses doivent s’appuyer sur les chiffres fournis dans le snapshot, pas sur l’invention.

## Vérification automatique (DB + Ollama)

Depuis le dossier `backend/`, utilisez l’interpréteur du **venv** (pas le `python3` système, souvent sans Flask) :

```bash
cd backend
python3 -m venv .venv   # une seule fois
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python3 features/chatbot_assistant/verify_chatbot_prompts.py
```

Si vous lancez `PYTHONPATH=. python3 …` et que Flask manque, le script tente de se relancer tout seul avec `backend/.venv/bin/python3` ou `../.venv/bin/python3` lorsqu’il existe.

Par défaut : compte `admin@test.com` / `admin123`. Options : `--email`, `--password`.

Le script appelle `/api/chatbot/chat` pour chaque question et contrôle que les **entiers attendus** (même logique que l’API) apparaissent dans la réponse, ou que les **routes** attendues sont citées pour les questions navigation. Nécessite **Ollama** joignable (`OLLAMA_*` dans `.env`).

---

## Anglais — comptages & agrégats

1. How many CSR plans do I have?
2. How many plans are in DRAFT vs SUBMITTED vs VALIDATED?
3. Break down my plans by year.
4. How many planned activities do I have in total?
5. How many activities by status?
6. How many realized CSR rows do I see?
7. How many site-linked documents are in my scope?
8. How many plans and how many activities — one line each?

## Français — comptages

9. Combien de plans CSR ai-je ?
10. Répartition de mes plans par année.
11. Combien d’activités planifiées au total ?
12. Combien d’activités réalisées (lignes) ?
13. Combien de documents liés aux sites ?

## Listes / échantillons (charge un peu plus de contexte)

14. List a few of my recent CSR plans with site and year.
15. Show sample planned activities I can access.
16. Liste-moi quelques plans avec site et année.

## Navigation & usage de l’app

17. Where do I open annual CSR plans in the app?
18. How do I go to planned activities from the menu?
19. Which routes exist for documents and change requests?
20. Comment accéder aux activités réalisées ?
21. Où trouver la validation des plans ?

## Filtres / explication UI (sans inventer de chiffres)

22. I see fewer plans on screen than your total — why?
23. Why might my plan count differ from the list view?

## Périmètre sites / rôle

24. Which site codes are in my data scope?
25. Am I a corporate user with access to all sites or only some?

## Questions vagues (doit rester court, éventuellement routes)

26. What can you help me with?
27. Résume ce que je peux faire dans CSR Insight.

## Documentation RAG (si index Chroma ingéré)

28. What is a CSR plan versus a planned activity?
29. What is the difference between planned and realized activities?
30. Explique le workflow d’un utilisateur site.

---

## À éviter comme “test de vérité” (le modèle ne doit pas inventer)

- Donne-moi le budget exact du plan X sans qu’il soit dans USER_DATA.
- Liste toutes les activités de l’année 2030.
- Quel est l’email d’un autre utilisateur ?

Ces questions servent à vérifier que le bot **refuse ou reste prudent** plutôt que d’halluciner.
