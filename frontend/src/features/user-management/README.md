# User Management – Gestion des utilisateurs

Module frontend de gestion des utilisateurs, authentification et profil pour CSR Insight.

---

## Vue d'ensemble

Le module **user-management** couvre :

- **Authentification** : connexion (login), déconnexion (logout), sessions JWT
- **Profil** : page « Mon Profil » pour consulter ses informations et changer son mot de passe
- **Administration** (corporate) : création et gestion des utilisateurs, assignation des sites

---

## Structure des dossiers

```
user-management/
├── login/              # Connexion
│   ├── login.ts        # Composant de login
│   ├── login.html      # Template
│   └── auth-api.ts     # API auth (login, logout, profile, change-password)
├── api/
│   └── users-api.ts    # API CRUD utilisateurs (corporate only)
├── users-list/         # Liste des utilisateurs
│   ├── users-list.ts   # Composant
│   └── users-list.html # Template
├── user-detail/        # Détail utilisateur (gestion sites)
│   ├── user-detail.ts  # Composant
│   └── user-detail.html# Template
├── profile-settings/   # Mon Profil / Paramètres
│   ├── profile-settings.ts
│   ├── profile-settings.html
│   └── profile-settings.css
├── models/             # Interfaces TypeScript
│   ├── user.model.ts
│   ├── user-session.model.ts
│   └── user-site.model.ts
└── README.md           # Ce fichier
```

---

## Routes

| Route | Composant | Accès | Description |
|-------|-----------|-------|-------------|
| `/login` | Login | Public | Page de connexion |
| `/account/profile` | ProfileSettingsComponent | Tous (auth) | Mon Profil : infos perso, notifications, préférences |
| `/admin/users` | UsersListComponent | Corporate | Liste des utilisateurs |
| `/admin/users/:id` | UserDetailComponent | Corporate | Détail utilisateur, gestion sites |

---

## Fichiers et responsabilités

### `login/login.ts`
- Page de connexion avec formulaire email/password
- Option « Se souvenir de moi » (stockage token dans `localStorage` ou `sessionStorage`)
- Utilise `AuthService.login()`, redirige vers dashboard en cas de succès

### `login/auth-api.ts`
- `AuthApi` : client HTTP pour `/api/auth`
- **login** : `POST /api/auth/login`
- **logout** : `POST /api/auth/logout`
- **getMe** : `GET /api/auth/me` (validation session)
- **getProfile** : `GET /api/auth/profile` (profil complet)
- **changePassword** : `PUT /api/auth/change-password`

### `api/users-api.ts`
- `UsersApi` : client HTTP pour `/api/users` (corporate only)
- **list** : liste des utilisateurs
- **get** : utilisateur avec sites
- **create** : création SITE_USER
- **update** : mise à jour (nom, statut, mot de passe)
- **assignSites** : assignation des sites (remplace l’existant)
- **resetPassword** : génération d’un nouveau mot de passe

### `users-list/`
- Liste des utilisateurs dans un tableau
- Bouton « Nouvel utilisateur » : formulaire de création (nom, email, mot de passe, sites)
- Actions par utilisateur : activer/désactiver, générer mot de passe, lien vers détail

### `user-detail/`
- Page détail d’un utilisateur
- Actions : activer/désactiver, générer mot de passe
- Pour SITE_USER : gestion des sites (checkbox par site, bouton Enregistrer)

### `profile-settings/`
- Page « Mon Profil » / Paramètres
- Blocs : identité, informations personnelles, sécurité (mot de passe), notifications, préférences

### `models/`
- Interfaces TypeScript alignées avec le backend
- `User`, `UserSession`, `UserSite`

---

## Rôles

| Rôle | Backend | Frontend | Accès |
|------|---------|----------|--------|
| **Corporate** | `CORPORATE_USER` | `corporate` | Tout (admin, sites, profil) |
| **Site** | `SITE_USER` | `site` | Profil, plans/activités de ses sites |

Le mapping `CORPORATE_USER` → `corporate`, `SITE_USER` → `site` est fait dans `AuthService`.

---

## Dépendances

- **Core** : `AuthStore`, `AuthService`, `authGuard`, `roleGuard`
- **Site management** : `SitesApi` pour lister les sites (assignation, formulaire création)
- **HTTP** : `jwtInterceptor` ajoute le header `Authorization: Bearer <token>`

---

## Endpoints backend utilisés

See full API reference: [`../../../docs/API.md`](../../../docs/API.md)

### Auth (`/api/auth`)
- `POST /login` – Connexion
- `POST /logout` – Déconnexion
- `GET /me` – Vérification session
- `GET /profile` – Profil complet
- `PUT /change-password` – Changement de mot de passe

### Users (`/api/users`, corporate only)
- `GET /` – Liste
- `GET /:id` – Détail avec sites
- `POST /` – Création SITE_USER
- `PATCH /:id` – Mise à jour
- `POST /:id/sites` – Assignation des sites
- `POST /:id/reset-password` – Génération mot de passe
