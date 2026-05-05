---
audience: all
---

# CSR Insight — guide pour l’assistant (RAG)

Ce document aide l’assistant à répondre sur l’application. Les **chiffres réels** (nombre de plans, d’activités, etc.) viennent toujours du bloc **USER_DATA** ou de la ligne entre crochets au début du message utilisateur, pas de ce texte.

## Où trouver les écrans (menu latéral)

Dire à l’utilisateur d’utiliser le **menu latéral** (barre à gauche) : les modules y sont listés par nom. Pas besoin de citer des adresses techniques sauf si l’utilisateur demande explicitement une « route » ou une URL.

- **Accueil / tableau de bord** : entrée du menu latéral qui ouvre la vue d’ensemble après connexion (résumé, accès rapide aux modules).
- **Plans CSR annuels** : entrée du type « Plans CSR » ou « CSR plans » dans le menu latéral — création, liste et validation des plans par site et par année.
- **Activités planifiées** : entrée « Activités planifiées » / « Planned activities » dans le menu latéral.
- **Activités réalisées** : entrée « Activités réalisées » / « Realized » (saisie de ce qui a été fait, pièces jointes) dans le menu latéral.
- **Documents** : entrée « Documents » dans le menu latéral.
- **Demandes de changement** : entrée du menu liée aux demandes de modification (libellé selon la langue de l’app).
- **Sites** : section ou entrée « Sites » dans le menu latéral (selon les droits).
- **Utilisateurs et audit** : réservés aux rôles admin corporate — entrées du menu latéral du type « Utilisateurs », « Audit ».

En français on peut dire « dans le menu à gauche », « dans la barre latérale », « cliquez sur … dans le menu ». En anglais : « in the left-hand sidebar », « from the sidebar, choose … ».

## Statuts des plans CSR

Un plan est lié à un **site** et à une **année** (ex. 2024). États courants :

- **DRAFT** — brouillon, non soumis
- **SUBMITTED** — soumis, en attente de validation (souvent appelé « under review » en anglais)
- **VALIDATED** — validé, accepté
- **REJECTED** — rejeté
- **LOCKED** — verrouillé

Pour les questions « combien de plans », « brouillon vs validé », « en revue », utiliser les comptages fournis dans USER_DATA.

## Statuts des activités planifiées

Deux notions coexistent :

1. **Statut en base (`planned_activity.status`)** — état du **workflow** (brouillon, soumis pour validation d’activité, rejet lié à une demande de modification, etc.). Il sert surtout aux transitions et aux demandes de changement.

2. **Statut effectif (`effective_status` dans l’API)** — quand le **plan annuel** parent est **VALIDATED** ou **LOCKED**, l’application affiche un statut « métier » dérivé : par exemple **PLANNED** (année future du plan), **IN_PROGRESS** (année en cours), **COMPLETED** (année passée), **UNDER_REVIEW** (demande de modification ou soumission en cours), **REJECTED**, **CANCELLED**. Les totaux du chatbot dans **USER_DATA** utilisent ce statut effectif pour les questions « combien d’activités par statut ».

Les **lignes réalisées** (`realized_activity`) ne sont pas les mêmes que le tableau des activités planifiées : elles décrivent ce qui a été fait et saisi.

## Périmètre utilisateur

- **Utilisateur corporate** : peut voir plusieurs sites selon les droits ; parfois « tous les sites ».
- **Utilisateur site** : voit surtout les données des sites auxquels il est affecté.

Si USER_DATA indique un périmètre, ne pas inventer d’autres sites ou chiffres.

## Filtres et écarts de comptage

Si l’écran affiche moins de lignes que le total annoncé par l’assistant, causes fréquentes : filtres par **année**, **statut**, site, ou vue « planifié » vs « réalisé ». Rappeler brièvement de vérifier les filtres de la liste.

## RAG vs données live

- **KNOWLEDGE_BASE** (extraits ci-dessus) : documentation générale, workflows, vocabulaire.
- **USER_DATA** : comptes, totaux, échantillons et périmètre pour l’utilisateur connecté.

En cas de contradiction, **USER_DATA** l’emporte.
