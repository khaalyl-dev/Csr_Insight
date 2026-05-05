# CSR Insight – Gestion des activités RSE

Plateforme de gestion des activités de responsabilité sociétale des entreprises (CSR), développée avec **Angular 21** (frontend) et **Flask** (backend), connectée à **MySQL**.

---

## Prérequis

- **Python 3.10+** (recommandé : 3.12 LTS ; évitez les combinaisons Python 3.14 + `mysql-connector-python` 8.x sans mettre à jour les dépendances)
- **Node.js 20.19+** (LTS) et **npm 10+** (le dépôt fixe aussi `packageManager` pour npm 11)
- **MySQL 8+**
- **Git**

---

## Structure du projet

```
├── backend/          # API Flask (port 5001)
│   ├── app.py        # Point d'entrée
│   ├── config.py     # Configuration (env)
│   ├── init_db.py    # Création tables + données de test
│   └── features/     # Modules API (auth, users, sites, etc.)
├── frontend/         # Application Angular (port 4200)
│   ├── src/
│   └── proxy.conf.json   # Proxy API → backend
├── Database/         # Schéma et documentations base de données
└── README.md
```

---

## Installation et exécution

### 1. Cloner le dépôt

```bash
git clone https://github.com/khaalyl-dev/Csr_Insight.git
cd Csr_Insight
```

*(Si vous travaillez déjà dans le projet, restez à la racine du dépôt.)*

---

### 2. Base de données MySQL

1. Créer la base :

```sql
CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```


---

### 3. Backend (Flask)

```bash
cd backend
python3 -m venv .venv
# macOS / Linux :
source .venv/bin/activate
# Windows (PowerShell) : .venv\Scripts\Activate.ps1
# Windows (cmd) : .venv\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt
```

Créer un fichier `.env` à la racine de `backend/` :

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=votre_mot_de_passe
DB_NAME=csr_db
SECRET_KEY=change-me-in-production
```

**Créer les tables et charger les données de test :**

```bash
python3 init_db.py    # Crée toutes les tables + utilisateurs, sites et catégories de test
```

**Démarrer le serveur :**

```bash
python3 app.py
```

Le backend est accessible sur **http://localhost:5001**.

---

### 4. Frontend (Angular)

Dans un **nouveau terminal** :

```bash
cd frontend
npm ci
npm start
```

*(En développement quotidien, `npm install` convient aussi ; pour une réinstallation propre, préférez `npm ci` avec le `package-lock.json` du dépôt.)*

Le frontend est accessible sur **http://localhost:4200**.

Le proxy Angular redirige les requêtes `/api` vers `http://localhost:5001`.

---

## Tester l’application

### Comptes de test

| Email              | Mot de passe | Rôle     |
|--------------------|-------------|----------|
| `admin@test.com`   | `admin123`  | Corporate |
| `user@test.com`    | `password123` | Site     |
| `john@example.com` | `john123`   | Site     |

### Scénarios de test

1. **Connexion**
   - Aller sur http://localhost:4200/login
   - Se connecter avec `admin@test.com` / `admin123`
   - Vérifier la redirection vers le dashboard

2. **Dashboard**
   - Dashboard site affiché après connexion
   - Vérifier les statistiques et graphiques si disponibles

3. **Mon Profil** (tous les rôles)
   - Menu **Mon Profil** → `/account/profile`
   - Vérifier les infos utilisateur et la liste des sites (Site)
   - Tester le changement de mot de passe

4. **Gestion des utilisateurs** (Corporate uniquement)
   - Menu **Gestion Utilisateurs** → `/admin/users`
   - Créer un utilisateur
   - Activer/désactiver un utilisateur
   - Générer un mot de passe
   - Aller sur le détail d’un utilisateur et gérer les accès aux sites

5. **Sites**
   - Menu **Gestion des Sites** → `/sites`
   - Vérifier la liste des sites

6. **Déconnexion**
   - Cliquer sur **Déconnexion** dans la sidebar
   - Vérifier la redirection vers la page de login

---

## Tests unitaires

### Backend (Python)

```bash
cd backend
# Avec pytest (si configuré)
pytest
# Ou tests manuels via curl/Postman
```

### Frontend (Angular / Vitest)

```bash
cd frontend
npm test
```

---

## Endpoints API principaux

| Méthode | Route                        | Description                    |
|---------|------------------------------|--------------------------------|
| POST    | `/api/auth/login`            | Connexion                      |
| POST    | `/api/auth/logout`           | Déconnexion                    |
| GET     | `/api/auth/me`               | Validation de session          |
| GET     | `/api/auth/profile`          | Profil complet                 |
| PUT     | `/api/auth/change-password`  | Changement de mot de passe     |
| GET     | `/api/users`                 | Liste des utilisateurs (corporate) |
| GET     | `/api/users/:id`             | Détail utilisateur + sites     |
| POST    | `/api/users/:id/sites`       | Assignation des sites          |
| GET     | `/api/sites`                 | Liste des sites                |
| GET     | `/api/dashboard/site/summary`| Résumé dashboard site          |
| GET     | `/api/health`                | Health check                   |

Les routes protégées nécessitent le header :  
`Authorization: Bearer <token>`

---

## Dépannage

### Le backend ne démarre pas
- Vérifier que MySQL tourne et que la base `csr_db` existe
- Vérifier le fichier `.env` (mots de passe, port, etc.)
- Exécuter `init_db.py` si les tables sont absentes

### Le frontend affiche des erreurs 404 sur `/api/*`
- Vérifier que le backend écoute sur le port 5001
- Vérifier que `proxy.conf.json` pointe vers `http://localhost:5001`

---

## Licence

Projet académique – PFE.
