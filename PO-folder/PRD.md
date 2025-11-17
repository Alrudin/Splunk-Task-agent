# **Product Requirements Document – AI-Assisted Splunk TA Generator**

---

## **1. Executive Summary**

This internal system provides an AI-driven workflow that automates the process of ingesting new log sources into Splunk. By combining an LLM agent, vectorized Splunk knowledge, and an automated validation sandbox, the system dramatically reduces the time and effort needed to produce high-quality, CIM-compliant Splunk Technology Add-ons (TAs).

The system interacts with requestors needing new log ingestion, collects sample logs, generates Splunk ingestion logic, validates it inside a real Splunk instance, and delivers a finalized TA package.

This directly reduces engineering workload and accelerates time-to-ingestion, while improving consistency and reducing human error.

---

## **2. Product Vision**

> **To eliminate manual TA development effort by enabling an autonomous AI agent to generate, validate, and deliver complete Splunk ingestion packages — reliably, securely, and in a fraction of the time.**

---

## **3. Target Users & Personas**

| Persona               | Skill Level                  | Motivation                          |
| --------------------- | ---------------------------- | ----------------------------------- |
| **Log Requestor**     | No Splunk knowledge required | Wants logs onboarded quickly        |
| **Splunk Specialist** | Advanced                     | Wants to avoid manual TA creation   |
| **Knowledge Admin**   | Internal SME                 | Ensures system knowledge is updated |

All personas are internal.

---

## **4. Problem Statement**

Creating Splunk Technology Add-ons today requires expert Splunk knowledge, extensive parsing experience, and large amounts of back-and-forth customer communication. This introduces:

* Long onboarding delays
* High manual engineering cost
* Frequent field extraction errors
* Repeated work for similar log sources

---

## **5. Solution Overview**

The system will:

1. Guide requestors through structured questions using an AI-driven interview
2. Collect representative log samples
3. Use a vector database plus Splunk knowledge to understand format
4. Require human approval before generation begins
5. Generate:

   * `inputs.conf`
   * `props.conf`
   * `transforms.conf`
   * CIM mappings
   * Full TA directory structure
6. Launch a standalone Splunk container and validate the TA
7. Produce a downloadable `.tgz` TA and notify the requestor
8. Support manual override and re-validation by a Splunk expert

---

## **6. Success Criteria**

| Metric                                   | Goal                          |
| ---------------------------------------- | ----------------------------- |
| Time to onboard new logs                 | **↓ 80%** versus today        |
| Splunk engineering effort                | **↓ minimum 20%**             |
| Production ingestion & extraction errors | **Strong downward reduction** |
| % automated TA delivery                  | Increases quarterly           |

---

## **7. Functional Requirements**

| Feature                           | Acceptance Criteria                                  | Priority |
| --------------------------------- | ---------------------------------------------------- | -------- |
| Guided Request Interview          | Must collect ingestion-critical information          | P1       |
| Log Sample Upload                 | Max 500 MB sample size                               | P1       |
| **Human Verification Gate**       | Splunk expert must approve request before generation | P1       |
| TA Generation                     | Must generate full TA structure                      | P1       |
| Sandbox Validation                | Must ingest and validate logs via Splunk API         | P1       |
| **Manual Override & Re-Validate** | Experts may edit TA **without restrictions**         | P1       |
| Notification System               | Requestor receives completion/failure notice         | P1       |
| Debug Bundle                      | Must include TA + validation logs if failed          | P1       |
| Vector Knowledge Search           | Must use Pinecone                                    | P1       |
| Knowledge Upload UI               | PDF, Markdown, TA ZIP/TGZ                            | P2       |
| Sample Storage Toggle             | Must be enable/disable controllable                  | P2       |
| Parallel Validation Limit         | Configurable concurrency control                     | P2       |

---

## **8. Non-Functional Requirements**

* MUST support: SAML, OAuth, and local user auth
* MUST log **all human actions** (audit events)
* MUST log **all agent and system events** (debug-level system logs)
* MUST run fully containerized
* MUST allow whitelisting and blacklisting of external URLs
* MUST allow configuration of `MAX_PARALLEL_VALIDATIONS`
* MUST allow internal Ollama LLM endpoint selection

---

## **9. Technical Requirements**

### **Validation Execution**

* A **standalone Splunk container** MUST be launched for every validation run
* Generated TA MUST be installed into the test instance
* Log samples MUST be ingested
* Validation MUST query Splunk via REST API to verify:

  * Parsing and ingestion success
  * Field extraction correctness
  * CIM mapping validity where applicable
* Validation results MUST return a structured pass/fail report

### **TA Versioning**

* Each generated TA must be versioned:

  ```text
  TA-<source>-v1
  TA-<source>-v2
  ```

* Manual override MUST increment versioning

### **Debug Bundle Contents**

Must include:

```text
Full generated TA (even if invalid)
Splunk internal error logs
Validation engine logs
Optional: prompt parameters used
```

### **Audit Logging Must Capture**

* Identity of approving human reviewer
* TA generation start/end
* Manual override uploads
* Re-validation triggers
* Debug bundle downloads

---

## **10. Dependencies**

| Dependency       | Purpose                    |
| ---------------- | -------------------------- |
| Ollama LLM       | Splunk config generation   |
| Pinecone         | Vector store for knowledge |
| Object Storage   | Store TAs & samples        |
| Splunk Container | Validation engine          |
| SAML/OAuth       | Authentication             |

---

## **11. Deployment Requirements**

* MUST be runnable as containers
* MUST allow specification of Ollama host/IP/port
* MUST run on-prem (likely Kubernetes)
* System MAY browse the internet
* Allowed hosts MUST be whitelist-controlled

---

## **12. Release Plan**

| Phase   | Deliverable                  |
| ------- | ---------------------------- |
| Phase 0 | Manual prototype             |
| Phase 1 | MVP – TA generation only     |
| Phase 2 | Sandbox validation           |
| Phase 3 | Full human approval workflow |
| Phase 4 | Internal rollout             |
| Phase 5 | Continuous improvement       |

---

## **13. Open Questions**

**None — all resolved.**

---

## **14. Assumptions**

* Log requestors will **not** track status, only receive notification
* Human input approval is required before run
* Manual override will be required for certain log sources
* Sample retention may be disabled when required by compliance

---

## **15. Appendix – Example User Stories**

| As a…           | I want…                      | So that…                      |
| --------------- | ---------------------------- | ----------------------------- |
| Requestor       | A guided ingestion assistant | I don’t need Splunk knowledge |
| Splunk Engineer | A downloadable TA            | I can deploy immediately      |
| Knowledge Admin | Upload docs & prior TAs      | The model stays correct       |

---
