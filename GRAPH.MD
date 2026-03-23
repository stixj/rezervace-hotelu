# Grafy architektury — Rezervace hotelu

Přehled komponent, závislostí, **workflow** procesů a toků dat. Diagramy jsou v [Mermaid](https://mermaid.js.org/) — zobrazí je GitHub, GitLab i mnoho editorů (včetně náhledu Markdownu v Cursoru).

---

## 1. Běhové prostředí (localhost)

Jeden proces **Uvicorn** obsluhuje API i statický frontend ze stejného originu.

```mermaid
flowchart LR
    subgraph client [Klient]
        B[Prohlížeč]
    end
    subgraph server [Backend — Uvicorn]
        U[FastAPI app]
        S[StaticFiles /frontend]
    end
    subgraph data [Data a integrace]
        DB[(SQLite nebo DATABASE_URL)]
        M[SMTP / e-mail]
    end
    B -->|HTTP GET /, /js/*, /css/*| S
    B -->|HTTP /reservations, /health, /docs| U
    U --> DB
    U -.->|RECEPTION_EMAIL| M
```

- **Výchozí URL:** `http://localhost:8003` (nebo `127.0.0.1:8003`). Port a host: `PORT`, `HOST` v `.env`.
- **Databáze:** bez `DATABASE_URL` se použije `backend/hotel_local.db`.

---

## 2. Vrstvy backendu (závislosti modulů)

```mermaid
flowchart TB
    main[main.py]
    api[api/reservations.py]
    deps[api/dependencies.py]
    svc[application/reservation_service.py]
    sch[schemas/reservation.py]
    dbmod[infrastructure/database.py]
    models[infrastructure/models.py]
    email[infrastructure/email.py]

    main --> api
    main --> dbmod
    api --> deps
    api --> svc
    api --> sch
    deps --> dbmod
    svc --> sch
    svc --> models
    svc --> email
    dbmod --> models
```

**Směr závislostí:** HTTP vrstva (`api`) volá aplikační logiku (`application`), ta používá modely a infrastrukturu (`infrastructure`). Schémata Pydantic (`schemas`) oddělují API kontrakty od DB entit.

---

## 3. REST API — prefix `/reservations`

```mermaid
flowchart LR
    R[Router reservations]
    R --> C[POST "" — vytvoření]
    R --> L[GET "" — seznam]
    R --> G[GET /{id}]
    R --> P[PUT /{id}]
    R --> X[POST /{id}/cancel]
    R --> ST[POST /{id}/status]
```

Další endpointy v `main.py`: `GET /health`, OpenAPI na `/docs`, frontend pod `/` (kromě cest vyhrazených pro API).

---

## 4. Tok: vytvoření rezervace

```mermaid
sequenceDiagram
    participant FE as Frontend JS
    participant API as FastAPI
    participant SVC as reservation_service
    participant DB as SQLModel Session
    participant EM as email

    FE->>API: POST /reservations + JSON
    API->>SVC: create_reservation
    SVC->>SVC: validace bed_preference vs room_type
    SVC->>DB: insert ReservationRequest
    DB-->>SVC: uloženo
    SVC->>EM: e-mail recepci (RECEPTION_EMAIL)
    EM-->>SVC: ok / log chyby
    SVC-->>API: ReservationRead
    API-->>FE: 200 JSON
```

---

## 5. Entita v databázi

```mermaid
erDiagram
    reservation_request {
        uuid id PK
        string requester_name
        string requester_email
        string city
        date date_from
        date date_to
        string room_type
        string bed_preference
        string note
        string status
        string hotel_name
        string reservation_number
        datetime created_at
        datetime updated_at
        datetime cancelled_at
    }
```

Enumy v kódu: `RequestStatus`, `City`, `RoomType`, `BedPreference` — mapované na řetězce v DB.

---

## 6. Frontend → API

```mermaid
flowchart LR
    subgraph fe [frontend/]
        HTML[index.html]
        APP[js/app.js]
        CFG[js/config.js]
    end
    HTML --> CFG
    HTML --> APP
    APP -->|fetch same-origin| API["/reservations"]
```

`config.js` nastaví `window.__API_BASE__` (prázdný řetězec = stejný origin jako stránka). Query `?api=` umožní přepsat základ URL pro vývoj.

---

## 7. Workflow — životní cyklus stavu žádosti

Stavy odpovídají `RequestStatus` v `infrastructure/models.py`. Přechody provádí backend podle volaného endpointu a validací v `reservation_service`.

```mermaid
stateDiagram-v2
    [*] --> NEW: POST /reservations
    NEW --> IN_PROGRESS: POST .../status
    NEW --> BOOKED: POST .../status
    NEW --> CANCELLED: cancel nebo status
    IN_PROGRESS --> BOOKED: POST .../status
    IN_PROGRESS --> CANCELLED: cancel nebo status
```

- Přechod do **BOOKED** přes `POST .../status` vyžaduje v těle `hotel_name` a `reservation_number`.
- Ze stavu **BOOKED** žadatel **nesmí** `PUT` ani `POST .../cancel` (HTTP 400).
- Ve stavu **CANCELLED** žadatel **nesmí** `PUT` (400); opakované `cancel` vrátí již zrušený záznam.
- Další změny stavu z backoffice řeší stejný endpoint `POST .../status` (bez omezení „žadatele“ jako u `PUT`/`cancel`).

**Pravidla v kódu (zjednodušeně):**

| Stav        | Žadatel: `PUT` údajů | Žadatel: `POST .../cancel` | Interní: `POST .../status` |
|------------|----------------------|----------------------------|----------------------------|
| NEW        | ano (stejný e-mail)  | ano                        | ano                        |
| IN_PROGRESS| ano                  | ano                        | ano                        |
| BOOKED     | ne (400)             | ne (400)                   | ano (např. doplnění polí)  |
| CANCELLED  | ne (400)             | vrátí stav zrušené        | záleží na volbě statusu    |

Při přechodu na **BOOKED** musí tělo požadavku obsahovat `hotel_name` a `reservation_number`; žadateli se odešle potvrzovací e-mail (`infrastructure/email.py`).

---

## 8. Workflow — role a kanály (žadatel vs recepce / backoffice)

```mermaid
flowchart TB
    subgraph public [Veřejný web — frontend]
        F1[Vyplnění formuláře]
        F2[Odeslání POST /reservations]
        F3[Vyhledání podle UUID\nGET /reservations/{id}]
        F1 --> F2 --> OK[Zobrazení UUID a stavu NEW]
        F3 --> STAV[Zobrazení stavu a detailů]
    end
    subgraph api [API — také /docs, curl, integrace]
        E1[PUT /reservations/{id}\n+ e-mail žadatele]
        E2[POST .../cancel\n+ e-mail žadatele]
        E3[POST .../status\nstav, hotel, číslo]
    end
    subgraph notify [Notifikace]
        M1[E-mail recepci\nRECEPTION_EMAIL]
        M2[E-mail žadateli\npři BOOKED]
    end
    F2 --> M1
    E1 --> M1
    E2 --> M1
    E3 --> M2
    R[Recepce / admin] --> E3
    Z[Žadatel] --> E1
    Z --> E2
```

- **Frontend** dnes implementuje hlavně **novou žádost** a **dotaz podle UUID**; úpravy, zrušení a změna stavu jsou určené pro volání z API (Swagger, skript, interní nástroj).
- Ověření identity žadatele u `PUT` a `cancel` je **e-mailem** shodným s uloženým záznamem (403 při nesouladu).

---

## 9. Workflow — uživatelská cesta na stránce (UI)

```mermaid
flowchart TD
    A[Načtení /] --> B{Formulář nové žádosti}
    B --> C{Validace dat v prohlížeči\nnapř. datum od/do}
    C -->|chyba| B
    C -->|OK| D[fetch POST /reservations]
    D -->|chyba sítě / API| E[Chybová hláška]
    D -->|422/400| E
    D -->|200| F[Úspěch + UUID + stav]
    A --> G[Formulář dotazu UUID]
    G --> H[GET /reservations/{id}]
    H -->|404 / chyba| I[Chybová hláška]
    H -->|200| J[Detail stavu, město, termín, hotel/číslo]
```

---

## 10. Workflow — lokální vývoj (spuštění)

```mermaid
flowchart LR
    S[run_local.ps1\nnebo run_local.bat] --> V[venv + pip install]
    V --> U[python main.py\nUvicorn]
    U --> L[http://localhost:8003]
    L --> FE[Frontend + API]
```

Volitelně v `backend/.env`: `DATABASE_URL`, `HOST`, `PORT`, `UVICORN_RELOAD`, `RECEPTION_EMAIL`, SMTP proměnné pro reálné e-maily.

---

*Soubor slouží jako rychlá mapa projektu; při větších změnách architektury a procesů ho aktualizujte.*
