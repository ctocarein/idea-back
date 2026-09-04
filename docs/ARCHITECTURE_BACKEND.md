# ARCHITECTURE BACKEND — IDEAXION

**Structure du backend FastAPI : couches, IAM, permissions, onboarding, patterns transverses.**
Document de référence pour le dev backend · Posture CTO · v2.0 (FastAPI) · Confidentiel — Ideaxion.

> Ce document décrit *comment le backend est structuré et pourquoi*. Il est subordonné au périmètre produit (GUIDE.md) et à la charte front. En cas de doute sur une route ou une table, **le périmètre fait foi** ; sur une convention de code, **ce document fait foi**.
>
> **Changement majeur v2.0 :** bascule de Go vers **Python / FastAPI**, motivée par la nature IA-centrée du produit (écosystème LLM natif Python, génération OpenAPI automatique via Pydantic alignée avec `openapi-typescript` côté front). Les décisions structurantes du backend Go (séparation en couches, audit transactionnel, résilience, jobs Postgres, presigned storage) sont **conservées** et transposées aux idiomes FastAPI.

---

## 0. Convention de langue du code

Règle non négociable, appliquée partout :

- **Le code est en anglais** : noms de variables, fonctions, classes, modules, tables, colonnes, valeurs d'enum, clés JSON.
- **Les commentaires de code sont en français** : tout `#`, toute docstring explicative.
- La documentation, les libellés produit et les messages destinés à l'utilisateur final restent en français (gérés via i18n, pas en dur dans la logique).

```python
class Invitation(Base):
    # Une invitation nominative émise par un admin pour un mentor ou un autre admin.
    # Le token n'est jamais stocké en clair : on garde uniquement son hash.
    __tablename__ = "invitations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(index=True)
    role: Mapped[Role]                       # rôle cible accordé à l'acceptation
    token_hash: Mapped[str]                  # hash SHA-256 du token envoyé par email
    status: Mapped[InvitationStatus]
```

---

## 1. Principes directeurs

Six règles qui ne se négocient pas. Tout le reste en découle.

1. **API-first.** Le backend est la seule source de vérité métier. Next.js ne fait que consommer `/api/v1`. Aucune règle métier ne vit dans le front. Le schéma OpenAPI est généré automatiquement par FastAPI et sert de contrat typé au front.
2. **Séparation en couches.** Un flux ne saute jamais une couche : `router → service → repository → DB`. Le `router` ne touche jamais la DB ; le `repository` ne connaît jamais le HTTP.
3. **`core` est technique, les features sont métier.** `app/core/` contient des clients et utilitaires sans métier (DB, cache, sécurité, storage, llm). Chaque feature (`app/iam`, `app/projects`…) contient son propre métier, isolé.
4. **Tout est asynchrone de bout en bout.** SQLAlchemy async + asyncpg, httpx async, Redis async. Tout traitement lourd ou faillible (analyse LLM, email, PDF) passe par la file de jobs, jamais dans la requête HTTP.
5. **Tout I/O externe est faillible.** Chaque appel sortant (LLM, MinIO, mailer) a un timeout, une stratégie de retry, un circuit breaker et un mode dégradé. Invariant, pas option.
6. **Tout est traçable.** Action sensible → `audit_logs`, **dans la même transaction** que l'action. Appel externe → log structuré. Job → statut et `error_message`.

---

## 2. Vue d'ensemble

```
                          ┌─────────────────────────────┐
                          │      Next.js (consommateur)  │
                          └──────────────┬──────────────┘
                                         │ HTTP REST /api/v1  (+ OpenAPI auto)
                          ┌──────────────▼──────────────┐
                          │        app.main:app          │
                          │  routers → dependencies →    │
                          │  (auth, permissions, guards) │
                          └──────────────┬──────────────┘
                                         │ appelle
                          ┌──────────────▼──────────────┐
                          │   app/<feature>/service.py   │  ← logique métier
                          └──────────────┬──────────────┘
                          ┌──────────────▼──────────────┐
                          │ app/<feature>/repository.py  │  ← accès données (SQLAlchemy)
                          └───┬─────────────┬───────────┘
                              │             │
                  ┌───────────▼──┐    ┌─────▼──────┐
                  │  PostgreSQL  │    │   Redis    │
                  └──────────────┘    └────────────┘

  app.worker (process séparé) ── poll ──> table `jobs` (FOR UPDATE SKIP LOCKED)
        │
        └── exécute run_diagnostic / send_email / action_reminder / purge_drafts
            via les mêmes app/<feature>/service + app/core/* (llm, storage, mailer…)
```

**Jobs différés et récurrents.** `enqueue(scheduled_at=…)` suffit : la boucle de claim
filtre déjà sur `scheduled_at <= now()`. Un rappel à J+7 est donc un simple `enqueue` daté,
et une tâche quotidienne (`purge_drafts`) se replanifie elle-même en fin d'exécution,
amorcée au démarrage du worker. **Il n'y a pas de planificateur externe, et il n'en faut
pas** : en ajouter un pour deux tâches serait une dépendance de plus à exploiter.
L'`idempotency_key` — datée pour les récurrentes, portant l'identifiant du bilan pour les
rappels — garantit qu'un rejeu ne duplique rien.

Deux points d'entrée, **un seul code base** :
- `app.main:app` : serveur HTTP (uvicorn/gunicorn). Répond vite, délègue le lourd.
- `app.worker` : process asynchrone qui draine la table `jobs`.

Les deux partagent `app/` (features + core). Le worker n'est pas un service à part : c'est un autre point d'entrée qui réutilise les mêmes services.

**Infra (résidence des données privilégiée) :** PostgreSQL, Redis, et **MinIO** (S3-compatible, hébergement local) pour le stockage objet. Les LLM par défaut sont **DeepSeek / Mistral** (coût + résidence), OpenAI/Gemini en option — le tout derrière l'abstraction `app/llm` (§10).

---

## 3. Arborescence complète

Organisation **feature-first** (cohérente avec le front feature-first). Chaque feature est un dossier autonome avec ses couches.

```text
/backend
├── app/
│   ├── main.py                 # app factory FastAPI : lifespan, middlewares, montage des routers
│   ├── worker.py               # entrypoint worker : boucle de polling de la table jobs
│   │
│   ├── core/                   # TECHNIQUE — aucun métier
│   │   ├── config.py           # pydantic-settings, validation fail-fast au démarrage
│   │   ├── database.py         # async engine, session factory, helper de transaction
│   │   ├── cache.py            # client Redis (cache, rate-limit, sessions)
│   │   ├── security.py         # hash argon2, création/vérif JWT, tokens d'invitation
│   │   ├── logging.py          # logging structuré JSON (structlog)
│   │   ├── errors.py           # enveloppe d'erreur uniforme + exception handlers
│   │   ├── pagination.py       # pagination cursor/offset standard
│   │   └── resilience.py       # timeout, retry/backoff, circuit breaker (transverse)
│   │
│   ├── iam/                    # IDENTITÉ, RÔLES, PERMISSIONS, AUTH  ← cœur de ce document
│   │   ├── router.py           # /auth/*, /me
│   │   ├── service.py          # register, login, refresh, logout, grant/revoke
│   │   ├── repository.py       # users, roles, permission_grants, sessions
│   │   ├── schemas.py          # DTO Pydantic (entrée/sortie)
│   │   ├── models.py           # User, PermissionGrant, RefreshToken
│   │   ├── permissions.py      # catalogue de permissions + matrice rôle→permissions
│   │   ├── dependencies.py     # get_current_user, require, resource guards
│   │   └── invitations.py      # invitations admin/mentor : modèle + service + routes
│   │
│   ├── onboarding/             # ORCHESTRATION onboarding porteur + investisseur ← focus
│   │   ├── router.py           # /onboarding/founder, /onboarding/investor
│   │   ├── service.py          # crée user + profil + projet/club en une transaction
│   │   └── schemas.py
│   │
│   ├── projects/               # projets + machine à états (sous-ensemble MVP, reste en v2)
│   ├── diagnostics/            # Radar de Collision, piloté par catégorie (secteur + archétype)
│   ├── reports/                # bilan / "tableau de compréhension" (essence/viabilité/scalabilité)
│   ├── mentors/                # marketplace mentors deux niveaux (coach / mentor-certificateur)
│   ├── investors/              # Club Financeurs (profil, curation)
│   ├── documents/              # upload presigned MinIO, data room
│   ├── notifications/          # notifications in-app + emails (via jobs) + désabonnement
│   ├── jobs/                   # file d'attente Postgres : enqueue, claim, retry
│   ├── audit/                  # journalisation des actions sensibles
│   │
│   ├── llm/                    # ABSTRACTION LLM — providers interchangeables (§10)
│   │   ├── base.py             # protocole LLMProvider
│   │   ├── deepseek.py         # provider par défaut
│   │   ├── mistral.py          # provider par défaut / fallback
│   │   ├── openai.py           # optionnel
│   │   ├── gemini.py           # optionnel
│   │   └── factory.py          # sélection du provider selon la config
│   │
│   └── _v2/                    # FEATURES DIFFÉRÉES — architecturées, non câblées en MVP
│       ├── payments/           # mobile money (CinetPay/PayDunya/Wave/Orange) + Stripe diaspora
│       ├── signatures/         # signature électronique (sprint de certification)
│       ├── certification/      # sprint + double sign-off mentor-certificateur
│       └── dealflow/           # mise en relation porteur↔investisseur
│
├── alembic/                    # migrations versionnées (up/down)
│   ├── env.py
│   └── versions/
├── tests/
├── pyproject.toml              # dépendances (uv / poetry)
├── .env.example                # toutes les variables, sans valeurs secrètes
├── Dockerfile                  # build api + worker (même image, commande différente)
├── Makefile                    # migrate, seed, test, lint, run
└── README.md
```

**Règle de lecture rapide :** si un fichier importe `fastapi`/`APIRouter`, c'est un `router` ; s'il importe `sqlalchemy`/la `Session`, c'est un `repository` ; s'il fait les deux, **c'est un bug de couche**.

**Périmètre MVP :** tout `app/_v2/` est présent dans l'architecture mais **non monté** sur le routeur principal en phase freemium. On architecture pour la v2, on ne construit que le MVP (§17).

---

## 4. Les trois couches

Chaque feature suit la même structure interne :

```text
app/projects/
├── router.py        # HTTP : décode la requête (Pydantic), appelle le service, encode la réponse
├── service.py       # MÉTIER : règles, transitions, orchestration, transactions, audit
├── repository.py    # DONNÉES : requêtes SQLAlchemy, mapping rows ↔ models
├── models.py        # entités ORM SQLAlchemy (Project, Status…)
├── schemas.py       # DTO Pydantic requête/réponse (jamais exposer l'ORM directement)
└── tests/           # tests unitaires (service avec repository mocké)
```

### 4.1. Responsabilité de chaque couche

| Couche | Connaît | Ne connaît jamais | Rôle |
| :--- | :--- | :--- | :--- |
| **Router** | HTTP, Pydantic, codes retour, `Depends` | SQL, règles métier | Traduire HTTP ↔ appel service. Validation de forme. Brancher auth/permissions. |
| **Service** | Règles métier, autres services | HTTP (`Request`), SQL brut | Orchestrer, décider, gérer les transactions, écrire l'audit. |
| **Repository** | SQLAlchemy, mapping | Règles métier, HTTP | Lire/écrire la DB. Une méthode = une intention de données. |

### 4.2. Injection de dépendances (testabilité)

Le service reçoit son repository et ses clients **par injection**, jamais en les instanciant lui-même. FastAPI câble ça via `Depends` ; en test, on injecte des mocks sans DB ni réseau.

```python
# app/projects/dependencies.py

def get_project_service(
    session: AsyncSession = Depends(get_session),
) -> ProjectService:
    # Le service ne sait pas d'où vient sa session ni son repo : on l'assemble ici.
    repo = ProjectRepository(session)
    auditor = AuditService(session)
    return ProjectService(repo=repo, auditor=auditor, cache=get_cache())
```

### 4.3. Flux d'une requête + garantie transactionnelle

Exemple : changer le statut d'un projet. **La transition, l'audit et l'invalidation de cache sont dans une seule transaction.** Soit tout réussit, soit rien. C'est le service qui porte cette garantie, jamais le router.

```python
# app/projects/service.py

class ProjectService:
    async def change_status(
        self, actor_id: UUID, project_id: UUID, next_status: Status
    ) -> Project:
        project = await self.repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        # Règle métier : la machine à états refuse tout saut illégal → 422.
        if not project.status.can_transition_to(next_status):
            raise IllegalTransitionError(project.status, next_status)

        # Une seule transaction : statut + audit + cache. Tout ou rien.
        async with self.repo.session.begin():
            await self.repo.update_status(project_id, next_status)
            await self.auditor.record(
                actor_id=actor_id,
                action="project.status_changed",
                entity="project",
                entity_id=project_id,
                old_value=project.status,
                new_value=next_status,
            )
            # En v2 : passage à "certified" → invalider le cache deal-flow investisseurs.
            if next_status is Status.CERTIFIED:
                await self.cache.invalidate(CacheKey.DEAL_FLOW)

        project.status = next_status
        return project
```

---

## 5. IAM — Identité, rôles, permissions

C'est la section centrale de cette réécriture. Le modèle est **hybride** : rôle (droits par défaut) **+** permissions explicites (capacités fines, ex. le pouvoir de certifier) **+** garde-fous au niveau ressource (propriété). Un check d'autorisation n'est jamais juste « quel rôle ? » : c'est « quelle permission **et** sur quelle ressource ».

### 5.1. Modèle d'identité

```python
# app/iam/models.py

class Role(str, Enum):
    # Quatre rôles de premier niveau. "founder" = le porteur de projet.
    ADMIN = "admin"
    MENTOR = "mentor"
    INVESTOR = "investor"
    FOUNDER = "founder"


class AccountStatus(str, Enum):
    PENDING_REVIEW = "pending_review"   # auto-inscrit, en attente de validation admin (mentor/investor)
    INVITED = "invited"                 # invité, pas encore activé (token non consommé)
    ACTIVE = "active"
    SUSPENDED = "suspended"


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]               # argon2id, jamais en clair
    full_name: Mapped[str]
    role: Mapped[Role]                       # rôle principal
    status: Mapped[AccountStatus] = mapped_column(default=AccountStatus.ACTIVE)
    created_at: Mapped[datetime]


class PermissionGrant(Base):
    # Permission accordée explicitement à un utilisateur, EN PLUS de celles de son rôle.
    # C'est le mécanisme qui transforme un "mentor" en "mentor-certificateur" :
    # on lui accorde la permission CERTIFICATION_SIGN, sans changer son rôle.
    __tablename__ = "permission_grants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    permission: Mapped[str]                  # ex. "certification:sign"
    granted_by: Mapped[UUID]                 # admin qui a accordé
    granted_at: Mapped[datetime]
```

> **Pourquoi rôle + permission plutôt que juste des rôles ?** Le mentor à deux niveaux (coach ouvert / mentor-certificateur à double signature) ne mérite pas deux rôles distincts : c'est le **même rôle** avec une **capacité en plus**. Modéliser ça comme une permission accordable évite la prolifération de rôles et rend le passage coach → certificateur réversible et auditable d'un seul `grant`.

### 5.2. Catalogue de permissions

Une permission est une chaîne `resource:action[:scope]`. Le catalogue est **statique, centralisé, exhaustif** — aucune permission n'existe hors de cette liste.

```python
# app/iam/permissions.py

class Permission(str, Enum):
    # --- Projets & diagnostic (MVP) ---
    PROJECT_READ_OWN = "project:read:own"        # voir ses propres projets
    PROJECT_READ_ASSIGNED = "project:read:assigned"  # mentor : projets qui lui sont assignés
    PROJECT_READ_ANY = "project:read:any"        # admin
    PROJECT_WRITE_OWN = "project:write:own"
    PROJECT_TRANSITION = "project:transition"    # déclencher une transition de statut
    DIAGNOSTIC_RUN = "diagnostic:run"            # lancer un Radar de Collision
    REPORT_READ_OWN = "report:read:own"

    # --- Mentorat / certification ---
    MENTOR_REVIEW = "mentor:review"              # coacher / commenter un projet assigné
    CERTIFICATION_SIGN = "certification:sign"    # [v2] pouvoir de signature du mentor-certificateur

    # --- Investisseur (Club) ---
    DEALFLOW_READ = "dealflow:read"              # [v2] consulter les projets certifiés
    INTRO_REQUEST = "intro:request"              # [v2] demander une mise en relation

    # --- Administration ---
    USER_MANAGE = "user:manage"
    INVITATION_SEND = "invitation:send"          # inviter mentor / admin
    INVESTOR_APPROVE = "investor:approve"        # valider une candidature au Club
    MENTOR_APPROVE = "mentor:approve"            # valider un mentor auto-inscrit
    PERMISSION_GRANT = "permission:grant"        # accorder CERTIFICATION_SIGN, etc.
    AUDIT_READ = "audit:read"
    JOBS_MANAGE = "jobs:manage"
```

### 5.3. Matrice rôle → permissions par défaut

```python
# app/iam/permissions.py

# Permissions accordées d'office à chaque rôle. Tout le reste passe par PermissionGrant.
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.FOUNDER: {
        Permission.PROJECT_READ_OWN,
        Permission.PROJECT_WRITE_OWN,
        Permission.PROJECT_TRANSITION,
        Permission.DIAGNOSTIC_RUN,
        Permission.REPORT_READ_OWN,
    },
    Role.MENTOR: {
        Permission.PROJECT_READ_ASSIGNED,
        Permission.MENTOR_REVIEW,
        # CERTIFICATION_SIGN n'est PAS ici : c'est un grant explicite (mentor-certificateur).
    },
    Role.INVESTOR: {
        Permission.DEALFLOW_READ,        # [v2] activé en v2
        Permission.INTRO_REQUEST,        # [v2]
    },
    Role.ADMIN: {
        # L'admin a tout. On l'exprime explicitement plutôt que par un wildcard,
        # pour que la matrice reste lisible et auditable.
        Permission.PROJECT_READ_ANY,
        Permission.USER_MANAGE,
        Permission.INVITATION_SEND,
        Permission.INVESTOR_APPROVE,
        Permission.MENTOR_APPROVE,
        Permission.PERMISSION_GRANT,
        Permission.AUDIT_READ,
        Permission.JOBS_MANAGE,
    },
}


def permissions_for(user: User, grants: set[Permission]) -> set[Permission]:
    # Permissions effectives = défauts du rôle UNION grants explicites.
    return ROLE_PERMISSIONS.get(user.role, set()) | grants
```

### 5.4. Garde-fous au niveau ressource (propriété)

La permission dit *quel type d'action* ; le garde-fou dit *sur quelle instance*. Un porteur a `PROJECT_READ_OWN` mais ne doit voir **que ses** projets ; un mentor **que les** projets qui lui sont assignés ; un investisseur **que les** projets `certified`.

```python
# app/iam/dependencies.py

async def guard_project_access(
    project: Project, user: User, perms: set[Permission]
) -> None:
    # On combine permission ET appartenance. Avoir la permission ne suffit pas.
    if Permission.PROJECT_READ_ANY in perms:
        return                                   # admin : tout
    if Permission.PROJECT_READ_OWN in perms and project.owner_id == user.id:
        return                                   # porteur : son projet
    if (
        Permission.PROJECT_READ_ASSIGNED in perms
        and await mentor_is_assigned(user.id, project.id)
    ):
        return                                   # mentor : projet assigné
    if (
        Permission.DEALFLOW_READ in perms
        and project.status is Status.CERTIFIED
    ):
        return                                   # [v2] investisseur : projets certifiés
    raise ForbiddenError("project")
```

### 5.5. Dépendances FastAPI — câblage de l'autorisation

L'auth et les permissions se branchent **déclarativement** sur chaque route, via `Depends`. Le router reste propre ; toute la logique d'autorisation vit dans `iam/dependencies.py`.

```python
# app/iam/dependencies.py

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    # Décode le JWT (HMAC-SHA256), charge l'utilisateur et ses permissions effectives.
    payload = decode_access_token(token)         # lève 401 si invalide/expiré
    user = await UserRepository(session).get_by_id(payload.sub)
    if user is None or user.status is not AccountStatus.ACTIVE:
        raise UnauthenticatedError()
    grants = await UserRepository(session).load_grants(user.id)
    return AuthContext(user=user, permissions=permissions_for(user, grants))


def require(*needed: Permission):
    # Fabrique une dépendance qui exige une ou plusieurs permissions.
    async def _checker(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not set(needed).issubset(ctx.permissions):
            raise ForbiddenError(missing=set(needed) - ctx.permissions)
        return ctx
    return _checker
```

Usage dans un router — lisible d'un coup d'œil :

```python
# app/projects/router.py

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    ctx: AuthContext = Depends(require(Permission.PROJECT_WRITE_OWN)),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectOut:
    # La permission est vérifiée AVANT d'entrer ici. Le service se concentre sur le métier.
    return await svc.create(owner_id=ctx.user.id, data=body)
```

### 5.6. Authentification — JWT, refresh, sessions

| Élément | Choix | Détail |
| :--- | :--- | :--- |
| **Hash mot de passe** | `argon2id` | Via `argon2-cffi`. Jamais de mot de passe en clair, ni en log. |
| **Access token** | JWT HMAC-SHA256, **15 min** | Porte `sub` (user id) et `role`. Les permissions fines sont rechargées côté serveur, pas mises dans le token (révocation immédiate possible). |
| **Refresh token** | opaque, **rotatif**, 30 j | Stocké hashé en base (`refresh_tokens`) + miroir Redis. Rotation à chaque usage ; réutilisation d'un token déjà consommé → révocation de toute la chaîne (détection de vol). |
| **Logout** | révocation | Supprime la session Redis + invalide le refresh courant. |
| **Rate-limit** | Redis | Sur `/auth/login` et `/auth/register` (anti brute-force). |

---

## 6. Invitations — admin & mentor

Deux chemins d'entrée pour mentors et admins. Le chemin **principal** est l'invitation nominative par un admin ; l'auto-inscription existe mais passe par une **validation**.

### 6.1. Modèle

```python
# app/iam/invitations.py

class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(index=True)
    role: Mapped[Role]                       # MENTOR ou ADMIN
    # Permissions pré-accordées à l'acceptation. Ex. {CERTIFICATION_SIGN} pour
    # créer directement un mentor-certificateur plutôt qu'un simple coach.
    granted_permissions: Mapped[list[str]] = mapped_column(default=list)
    cv_document_id: Mapped[UUID | None]      # CV joint par l'admin (curation mentor)
    token_hash: Mapped[str]                  # hash du token ; le token clair n'existe que dans l'email
    status: Mapped[InvitationStatus] = mapped_column(default=InvitationStatus.PENDING)
    invited_by: Mapped[UUID]
    expires_at: Mapped[datetime]             # ex. +7 jours
    created_at: Mapped[datetime]
```

### 6.2. Flux d'invitation (chemin principal mentor)

```
1. [admin]  POST /admin/invitations
            { email, role: "mentor", granted_permissions: ["certification:sign"],
              cv_document_id }
            → require(INVITATION_SEND)

2. [service]  dans UNE transaction :
        - génère un token aléatoire (secrets.token_urlsafe), n'en stocke que le HASH
        - crée Invitation(status=pending, expires_at=+7j)
        - audit.record("invitation.sent", actor=admin, entity=invitation)
        - enqueue job send_email(invitation_link)   ← le lien porte le token EN CLAIR

3. [mentor] clique le lien → GET /invitations/{token}  → écran d'activation (front)
        - le service re-hashe le token reçu, le compare, vérifie status+expiration

4. [mentor] POST /invitations/{token}/accept  { full_name, password }
        → dans UNE transaction :
            - crée User(role=mentor, status=active, password_hash=argon2(...))
            - applique granted_permissions → PermissionGrant (ici: certification:sign)
            - Invitation.status = accepted
            - audit.record("invitation.accepted")
        → renvoie une session (access + refresh)
```

Points durs imposés : token **jamais stocké en clair**, **usage unique** (status passe à `accepted`), **expiration** stricte, **audit** des deux bouts (envoi et acceptation). L'invitation **admin** suit exactement le même flux avec `role: "admin"`.

### 6.3. Auto-inscription mentor (chemin secondaire, marketplace coaching)

Un mentor peut se présenter spontanément, mais il **n'est pas actif** tant qu'un admin ne l'a pas validé.

```
1. POST /mentors/apply  { full_name, email, password, cv_document_id, expertise }
   → crée User(role=mentor, status=PENDING_REVIEW)   [pas de permission tant que pending]
2. [admin] GET /admin/mentors?status=pending_review
3. [admin] POST /admin/mentors/{id}/approve   → require(MENTOR_APPROVE)
        - User.status = active
        - éventuellement grant CERTIFICATION_SIGN si promu mentor-certificateur
        - audit + email de bienvenue
```

C'est la traduction directe du modèle « marketplace ouvert (coach) vs mentors-certificateurs curatés à double signature » : le **rôle** est le même, c'est le **statut** (actif) et la **permission** (`certification:sign`) qui distinguent les deux niveaux.

---

## 7. Onboarding — porteur & investisseur

Deux portes distinctes (cf. l'écran d'entrée du front : porte porteur en dégradé Aube, porte investisseur en teal). Chaque onboarding crée l'utilisateur **et** son contexte métier en une transaction.

### 7.1. Porteur (auto-inscription, gratuit)

Aligné sur l'écran d'onboarding en 3 étapes du front.

```python
# app/onboarding/schemas.py

class Archetype(str, Enum):
    DIGITAL = "digital"     # appli, plateforme, logiciel, service en ligne
    FIELD = "field"         # "terrain" : commerce, production, agro, service local, artisanat


class ProjectStage(str, Enum):
    IDEA = "idea"
    PROTOTYPE = "prototype"
    FIRST_CUSTOMERS = "first_customers"
    GROWING = "growing"


class EntryMode(str, Enum):
    GUIDED = "guided"       # "J'ai une idée à explorer" : interrogation étape par étape
    DOCUMENT = "document"   # "J'ai déjà un document" : dépose un BP, on l'analyse


class FounderOnboarding(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=6)
    archetype: Archetype
    sector: str
    stage: ProjectStage
    entry_mode: EntryMode
```

```python
# app/onboarding/service.py

class OnboardingService:
    async def onboard_founder(self, data: FounderOnboarding) -> OnboardingResult:
        # Un seul appel crée tout le contexte du porteur, de façon atomique.
        async with self.session.begin():
            user = await self.users.create(
                email=data.email,
                password_hash=hash_password(data.password),
                full_name=data.full_name,
                role=Role.FOUNDER,
                status=AccountStatus.ACTIVE,
            )
            # La "catégorie" (secteur + archétype) pilote tout le moteur de diagnostic.
            project = await self.projects.create(
                owner_id=user.id,
                sector=data.sector,
                archetype=data.archetype,
                stage=data.stage,
                status=Status.DRAFT,
            )
            await self.audit.record(
                actor_id=user.id, action="founder.onboarded",
                entity="project", entity_id=project.id,
            )
        # Le diagnostic n'est PAS lancé ici : c'est une action explicite ultérieure
        # (mode guided → questionnaire ; mode document → upload + job d'analyse).
        return OnboardingResult(user=user, project=project, tokens=issue_tokens(user))
```

### 7.2. Investisseur (Club Financeurs, curaté)

Le Club est l'actif stratégique — il est **curaté**. En phase de lancement l'accès est gratuit, mais le profil passe par une file de validation admin.

```python
# app/onboarding/schemas.py

class InvestorType(str, Enum):
    ANGEL = "angel"                 # business angel
    FUND = "fund"                   # fonds d'investissement
    FAMILY_OFFICE = "family_office"
    CORPORATE = "corporate"


class TicketRange(str, Enum):
    # Fourchettes en FCFA, alignées sur le front.
    UNDER_5M = "under_5m"
    FROM_5M_TO_25M = "5m_25m"
    FROM_25M_TO_100M = "25m_100m"
    OVER_100M = "over_100m"


class InvestorOnboarding(BaseModel):
    full_name: str
    organization: str | None = None
    email: EmailStr
    password: str = Field(min_length=6)
    investor_type: InvestorType
    ticket_range: TicketRange
    sectors_of_interest: list[str] = Field(default_factory=list)
```

```python
# app/onboarding/service.py

    async def onboard_investor(self, data: InvestorOnboarding) -> OnboardingResult:
        async with self.session.begin():
            user = await self.users.create(
                email=data.email,
                password_hash=hash_password(data.password),
                full_name=data.full_name,
                role=Role.INVESTOR,
                # Curaté : actif côté compte, mais le profil Club attend validation admin.
                status=AccountStatus.ACTIVE,
            )
            await self.investors.create_profile(
                user_id=user.id,
                organization=data.organization,
                investor_type=data.investor_type,
                ticket_range=data.ticket_range,
                sectors=data.sectors_of_interest,
                review_status="pending_review",   # entre dans la file de curation
            )
            await self.audit.record(
                actor_id=user.id, action="investor.applied", entity="investor_profile",
            )
        return OnboardingResult(user=user, tokens=issue_tokens(user))
```

L'admin valide ensuite via `POST /admin/investors/{id}/approve` (`require(INVESTOR_APPROVE)`), ce qui ouvre l'accès au deal-flow (effectif en v2). On capture le profil dès maintenant pour amorcer le Club, même si la mise en relation n'est livrée qu'en v2.

---

## 8. Projets & machine à états

La machine à états reste explicite : aucune transition implicite, tout saut illégal → `422`. **En MVP freemium, seul le segment "comprendre" est actif** ; le reste (sprint, certification, investisseurs) est architecturé mais inactif.

```python
# app/projects/models.py

class Status(str, Enum):
    # --- Segment MVP : "comprendre" (gratuit) ---
    DRAFT = "draft"                          # projet créé, pas encore de diagnostic
    DIAGNOSTIC_IN_PROGRESS = "diagnostic_in_progress"
    DIAGNOSTIC_COMPLETED = "diagnostic_completed"
    BILAN_READY = "bilan_ready"              # Radar + tableau de compréhension disponibles
    ARCHIVED = "archived"                    # terminal
    # --- Segment v2 : "transformer" (payant) ---
    SPRINT_OFFERED = "sprint_offered"        # [v2]
    SPRINT_SIGNED = "sprint_signed"          # [v2]
    SPRINT_IN_PROGRESS = "sprint_in_progress"  # [v2]
    DOSSIER_DELIVERED = "dossier_delivered"  # [v2]
    CERTIFIED = "certified"                  # [v2] double sign-off mentor-certificateur
    PRESENTED_INVESTORS = "presented_investors"  # [v2]
    IN_DISCUSSION = "in_discussion"          # [v2]
    FUNDED = "funded"                        # [v2] terminal
    REJECTED = "rejected"                    # terminal


# Transitions autorisées. En MVP, seules les transitions du segment "comprendre"
# sont câblées ; les transitions [v2] existent dans la table mais ne sont pas exposées.
ALLOWED_TRANSITIONS: dict[Status, list[Status]] = {
    Status.DRAFT: [Status.DIAGNOSTIC_IN_PROGRESS, Status.ARCHIVED],
    Status.DIAGNOSTIC_IN_PROGRESS: [Status.DIAGNOSTIC_COMPLETED, Status.ARCHIVED],
    Status.DIAGNOSTIC_COMPLETED: [Status.BILAN_READY],
    Status.BILAN_READY: [Status.SPRINT_OFFERED, Status.ARCHIVED],  # SPRINT_OFFERED = frontière v2
    # ... transitions v2 définies mais non exposées en MVP
}
```

Les modules qui déclenchent une transition (diagnostics, et en v2 signatures/certification) **n'écrivent jamais le statut directement** : ils appellent `ProjectService.change_status(...)`, qui porte la garantie transaction + audit (§4.3).

---

## 9. Diagnostic & Radar de Collision

Le moteur est **piloté par catégorie** : `secteur + archétype (digital/field)`. Il produit l'évaluation à six axes (Radar de Collision), rendue en « tableau de compréhension » (essence / viabilité / scalabilité). Le Radar sert aussi de **rubrique mentor** (unification structurelle assumée).

Flux (asynchrone, résilient) :

```
1. POST /projects/{id}/diagnostic   { mode: "guided" | "document" }
   → require(DIAGNOSTIC_RUN) + guard (projet appartient au porteur)
   → projects.change_status(→ diagnostic_in_progress)
   → enqueue job "run_diagnostic" { project_id, mode }
   → 202 Accepted (réponse immédiate)

2. [worker] claim "run_diagnostic"
   → diagnostics.service :
        - construit le prompt selon (secteur, archétype, réponses|document)
        - llm.complete(...)   via app/llm (DeepSeek/Mistral), timeout + circuit breaker
              ↳ si indisponible → job "retrying", projet reste in_progress
        - parse le résultat en 6 scores d'axes (Pydantic, parsing strict)
        - reports.service.create_bilan(...)   # tableau de compréhension
        - projects.change_status(→ diagnostic_completed → bilan_ready)
        - enqueue "send_email" (bilan prêt)
```

Le parsing du JSON LLM est **strict** (validation Pydantic) : une sortie malformée n'écrit jamais un bilan corrompu, elle relance ou bascule en revue manuelle.

---

## 10. Abstraction LLM (`app/llm`)

Le métier ne connaît **jamais** un fournisseur LLM concret. Il dépend d'un protocole ; la `factory` choisit le provider selon la config. C'est ce qui permet DeepSeek/Mistral par défaut (coût + résidence) et OpenAI/Gemini en option, sans toucher au métier.

```python
# app/llm/base.py

class LLMProvider(Protocol):
    # Tout provider expose la même surface. Le métier ne dépend que de ce protocole.
    async def complete(self, prompt: str, *, schema: type[BaseModel] | None = None) -> LLMResult:
        ...


# app/llm/factory.py

def get_llm(settings: Settings) -> LLMProvider:
    # Le provider par défaut est piloté par la config (résidence + coût d'abord).
    match settings.LLM_PROVIDER:
        case "deepseek": return DeepSeekProvider(settings)
        case "mistral":  return MistralProvider(settings)
        case "openai":   return OpenAIProvider(settings)   # optionnel
        case "gemini":   return GeminiProvider(settings)   # optionnel
        case _:          raise ConfigError("LLM_PROVIDER inconnu")
```

Chaque provider est enveloppé par `app/core/resilience` (timeout, retry sur erreurs transitoires, circuit breaker). LLM indisponible → mode dégradé (job rejoué, diagnostic en attente), jamais une erreur 500 silencieuse côté porteur.

---

## 11. File de jobs & worker (`app/jobs` + `app.worker`)

On **conserve le pattern Postgres** du backend Go (table `jobs` + `FOR UPDATE SKIP LOCKED`) plutôt qu'un broker externe : moins de dépendances, et la résidence des données reste dans Postgres. (Alternative possible : `arq` sur Redis — mais le job en base est préféré ici pour la traçabilité et la résidence.)

### 11.1. Cycle de vie

```
pending ──claim──> processing ──┬─ succès ─> completed
                                ├─ échec (retries restants) ─> retrying ─(backoff)─> pending
                                └─ échec (retries épuisés)  ─> failed ─> alerte admin
```

Backoff : 1 min → 5 min → 15 min, `max_retries = 3`.

### 11.2. Claim concurrent sûr

```sql
-- app/jobs/repository.py (claim) — plusieurs workers sans collision grâce à SKIP LOCKED
UPDATE jobs SET status = 'processing', started_at = now()
WHERE id = (
    SELECT id FROM jobs
    WHERE status IN ('pending', 'retrying')
      AND scheduled_at <= now()
    ORDER BY priority ASC, scheduled_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, type, payload, retry_count, max_retries;
```

### 11.3. Boucle du worker

```python
# app.worker — boucle simplifiée

async def run() -> None:
    registry = {
        "run_diagnostic": handle_run_diagnostic,
        "send_email": handle_send_email,
        "cleanup_expired": handle_cleanup_expired,   # cron quotidien
    }
    while True:
        job = await jobs_service.claim()
        if job is None:
            await asyncio.sleep(POLL_INTERVAL)        # ex. 2s, rien à faire
            continue
        try:
            await registry[job.type](job.payload)
        except Exception as exc:                       # noqa: BLE001 — on capture tout pour décider du retry
            await jobs_service.fail(job, exc)          # → retrying (backoff) ou failed (alerte)
            continue
        await jobs_service.complete(job)
```

---

## 12. Patterns transverses

### 12.1. Enveloppe d'erreur uniforme (`app/core/errors.py`)

Une seule forme de réponse d'erreur dans toute l'API, via des exception handlers FastAPI :

```json
{ "error": { "code": "ILLEGAL_TRANSITION", "message": "...", "details": [] } }
```

| Exception métier | HTTP |
| :--- | :--- |
| `ValidationError` (Pydantic / métier) | 400 |
| `UnauthenticatedError` | 401 |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` (ex. email pris) | 409 |
| `IllegalTransitionError`, règle métier | 422 |
| tout le reste | 500 (loggé, jamais détaillé au client) |

### 12.2. Audit transactionnel (`app/audit`)

Helper unique appelé **dans la même transaction** que l'action sensible (changement de statut, grant de permission, invitation, approbation, suppression RGPD). Capture `actor`, `action`, `entity`, `old/new`, IP, user-agent. Si l'audit échoue, la transaction échoue : **pas d'action sensible sans trace**.

### 12.3. Résilience des appels externes (`app/core/resilience.py`)

| Garde-fou | Implémentation |
| :--- | :--- |
| **Timeout** | `httpx` timeout par appel — LLM 30s, PDF 60s, MinIO 15s, mailer 10s. |
| **Retry + backoff** | 3 tentatives, délais croissants, uniquement sur erreurs transitoires (5xx, timeout). |
| **Circuit breaker** | 3 échecs consécutifs → circuit ouvert → bascule en fallback. |
| **Graceful degradation** | LLM down → diagnostic en attente, job rejoué. Email down → mise en file. |

### 12.4. Stockage MinIO presigned (`app/documents`)

Upload **direct client→MinIO** via presigned URL (l'API ne fait jamais transiter les octets) :

```
1. POST /documents/upload-url   → presigned PUT (expire 5 min) + validation type/taille (≤ 20 Mo)
2. le client PUT le fichier directement sur MinIO
3. POST /documents/confirm      → l'API crée l'entrée `documents` en base
```

Téléchargement (data room, CV mentor) : presigned GET (expire 24h) réservé aux porteurs de la bonne permission + garde-fou de propriété.

### 12.5. Webhooks idempotents (différé v2 : paiements, signatures)

Pattern conservé pour la v2 : vérifier la **signature** du provider → extraire l'**id d'événement** → insérer dans une table de déduplication (`UNIQUE`) → si conflit, `200` sans rien refaire ; sinon traiter en transaction. Mobile money (CinetPay/PayDunya/Wave/Orange) et Stripe diaspora suivront ce pattern.

### 12.6. Cache Redis (`app/core/cache.py`)

| Donnée | TTL | Invalidation |
| :--- | :--- | :--- |
| Sessions / refresh | 30 j | au logout / rotation |
| Rate-limit | 1 min / 1h | automatique |
| Liste deal-flow [v2] | 5 min | au passage projet → `certified` |
| Config plateforme | 1h | manuel (admin) |

---

## 13. Configuration & secrets (`app/core/config.py`)

`pydantic-settings`, validé **au démarrage** (fail-fast). Aucun secret dans le repo. `.env.example` liste toutes les variables sans valeurs.

```python
# app/core/config.py

class Settings(BaseSettings):
    # Si une variable requise manque, l'app refuse de démarrer (crash visible > erreur silencieuse).
    database_url: PostgresDsn
    redis_url: RedisDsn
    jwt_secret: SecretStr
    llm_provider: str = "deepseek"           # deepseek | mistral | openai | gemini
    deepseek_api_key: SecretStr
    mistral_api_key: SecretStr | None = None
    minio_endpoint: str
    minio_access_key: SecretStr
    minio_secret_key: SecretStr
    cors_origins: list[str] = []

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

---

## 14. Migrations (`alembic/`)

- Outil : **Alembic**. Une révision par changement, **toujours réversible** (`upgrade`/`downgrade` testés sur staging avant prod).
- Ordre : extensions + types ENUM d'abord, puis les tables dans l'ordre des dépendances (FK).
- `make migrate` applique ; `make seed` injecte un compte de démo par rôle (admin, mentor, mentor-certificateur, investor, founder).
- On versionne le schéma, jamais les modèles « auto-générés sans relecture » : chaque révision est relue.

---

## 15. Dépendances Python recommandées

| Besoin | Lib | Note |
| :--- | :--- | :--- |
| Framework HTTP | **FastAPI** + **uvicorn**/gunicorn | OpenAPI auto, validation Pydantic native. |
| ORM / DB | **SQLAlchemy 2.0 (async)** + **asyncpg** | Mapping typé, transactions, `SKIP LOCKED`. |
| Schémas / config | **Pydantic v2** + **pydantic-settings** | DTO + settings fail-fast. |
| Migrations | **Alembic** | Up/down versionnés. |
| Hash mot de passe | **argon2-cffi** | Argon2id. |
| JWT | **pyjwt** | HMAC-SHA256. |
| Cache / file | **redis** (async) | Sessions, rate-limit, cache. |
| HTTP client | **httpx** (async) | Clients LLM/MinIO maison, minces et mockables. |
| Stockage objet | **minio** (ou boto3 S3-compatible) | MinIO presigned. |
| Logging | **structlog** | JSON structuré. |
| Tests | **pytest** + **pytest-asyncio** + **httpx AsyncClient** | Unitaire + intégration. |
| Lint / format | **ruff** + **mypy** | Lint rapide + typage strict. |

Principe inchangé : **peu de dépendances, bien choisies**. Les clients externes (LLM, MinIO, mailer) restent minces derrière une interface mockable.

---

## 16. Tests

| Niveau | Cible | Comment |
| :--- | :--- | :--- |
| **Unitaire** | service métier | repository + clients `core/*` mockés. Couvre transitions, **permissions**, garde-fous de propriété, dégradation. ≥ 70 %. |
| **Intégration** | endpoints critiques | `httpx AsyncClient` + DB de test (conteneur). Vérifie router→service→repo réel. |
| **E2E** | parcours critiques | Côté front (Playwright). |

Priorité de test : **les cas `403`** (un porteur ne voit pas le projet d'un autre, un mentor non-certificateur ne peut pas signer), le **flux d'invitation** (token usage unique, expiration), les **deux onboardings**, la légalité des transitions de statut.

---

## 17. Périmètre — MVP freemium vs v2

| Domaine | MVP freemium (construit) | v2 (architecturé, différé) |
| :--- | :--- | :--- |
| IAM, rôles, permissions | ✅ complet (4 rôles, grants, garde-fous) | — |
| Invitations admin/mentor | ✅ | — |
| Onboarding porteur | ✅ | — |
| Onboarding investisseur (capture + curation) | ✅ profil + file de validation | deal-flow actif |
| Diagnostic / Radar / bilan ("comprendre") | ✅ | — |
| Marketplace mentor (coaching) | ✅ assignation + revue | industrialisation réseau |
| Sprint de certification ("transformer") | ❌ | ✅ `_v2/certification` + double sign-off |
| Signatures électroniques | ❌ | ✅ `_v2/signatures` |
| Paiements (mobile money + Stripe diaspora) | ❌ | ✅ `_v2/payments` |
| Deal-flow / mise en relation | ❌ | ✅ `_v2/dealflow` |

Discipline de séquençage : **valider ~10 projets manuellement** (diagnostic → bilan, parcours complet) avant d'industrialiser quoi que ce soit. Le code `_v2/` existe pour que l'architecture tienne, pas pour être branché trop tôt.

---

*Document d'architecture backend — posture CTO · FastAPI v2.0.*
*Conventions : code en anglais, commentaires en français. Aligné GUIDE.md (périmètre) et charte front (contrat OpenAPI).*
*Confidentiel — Ideaxion.*
