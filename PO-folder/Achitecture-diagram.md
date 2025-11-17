
# **System Architecture Diagram (Mermaid)**

```mermaid
flowchart LR
    subgraph UI["Web UI"]
        A1[Log Request Form]
        A2[Sample Upload]
        A3[Admin Knowledge Upload]
        A4[Review & Approval Dashboard]
        A5[Manual Override Interface]
        A6[Notification Display]
    end

    subgraph Backend["TA Generation & Control Service"]
        B1[Request Orchestrator]
        B2[LLM Agent Engine]
        B3[Validation Pipeline Manager]
        B4[TA Version Manager]
        B5[Audit/Event Logger]
        B6[Notification Service]
    end

    subgraph AI["LLM Stack"]
        C1[Prompt Builder]
        C2[Ollama / API Gateway]
        C3[Model Execution]
    end

    subgraph VectorDB["Vector Knowledge Store"]
        D1[Pinecone Index]
        D2[Splunk Docs Embeddings]
        D3[Historical TA Embeddings]
        D4[Sample Log Embeddings]
    end

    subgraph Storage["Object Storage"]
        E1[Uploaded Log Samples]
        E2[Generated TA Bundles]
        E3[Debug Artifacts]
    end

    subgraph Sandbox["Validation Environment"]
        F1[Ephemeral Splunk Container]
        F2[TA Installation]
        F3[Sample Log Ingestion]
        F4[REST API Search Validation]
    end

    subgraph Auth["Identity Provider"]
        G1[SAML Provider]
        G2[OAuth Provider]
    end

    %% UI to Backend
    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    A5 --> B4

    %% Backend to AI
    B2 --> C1
    C1 --> C2
    C2 --> C3

    %% AI to Vector DB
    C1 --> D1

    %% Backend to validation
    B3 --> F1
    F1 --> F2
    F2 --> F3
    F3 --> F4
    F4 --> B3

    %% Outputs
    B3 --> E2
    B3 --> E3
    B6 --> A6

    %% Storage paths
    A2 --> E1
    A3 --> D1

    %% Logging
    B5 -->|Audit Logs| Storage
    B5 -->|Debug Logs| Storage
    
    %% Auth
    UI <-->|Login| Auth

```

---

# **Legend**

| Component                | Purpose                                 |
| ------------------------ | --------------------------------------- |
| **Web UI**               | Requestor + Admin interaction           |
| **Backend Orchestrator** | Controls full workflow / state          |
| **LLM Engine**           | Generates TA configs + extraction logic |
| **Vector DB**            | Stores Splunk knowledge embeddings      |
| **Sandbox**              | Runs Splunk and validates ingestion     |
| **Storage**              | Holds samples, TA bundles, debug logs   |
| **Auth**                 | Provides SAML + OAuth login             |

---

# **Key Architectural Behaviors**

### 🔹 Request Flow

1. Request submitted via UI
2. Backend orchestrator validates inputs
3. Human approval required before generation
4. LLM agent retrieves embeddings from Pinecone
5. TA generated + versioned
6. Sandbox launched → TA tested → Result + debug artifacts stored
7. Requestor notified of success or failure

---

### 🔹 Manual Override Path

* Expert downloads TA
* Edits configs manually
* Re-uploads to UI
* Backend re-runs *only validation stage*
* New version tagged

---

### 🔹 Compliance Behaviors

* All human actions logged
* Log sample retention toggle (store vs auto-delete)
* Maximum parallel Splunk containers configurable
* Internet access restricted via whitelist/blacklist
