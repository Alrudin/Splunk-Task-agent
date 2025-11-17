# Clarification document

## 1 Product Objectives / Business Goals

- Reduce onboarding time for customers and reduce time speding developing SPlunk TAs
- Success is to reduce the time spend communicating with customers prior to developing  the TA and redude the development time it self to 20% less time spent on these cases
- This is an internal tool

## 2 Primary User Personas

- The primary user of this is the persosns requesting log ingestion into Splunk
- The requestor/customer do not have any special Splunk Knowledge, but the persons recieving the resulting Splunk TA and deploying it, is Splunk specialists.
- This is a tool for internal use

## 3 Expected workflow

1. User requests log onboarding

2. Agent asks clarifying questions (log source, format, fields required, etc.) CIM compliance must be done when possible.

3. User uploads log samples

4. Agent searches vector database + web sources for similar solutions

5. Agent generates:

    - Splunk inputs config

    - Props and transforms

    - Field extractions

    - CIM mapping

    - Full TA structure

    - Agent tests the TA inside a sandbox

6. Agent outputs downloadable TA (.tgz)

## 4 AI model requirements

- Model must be used by calling an API.
- The model can be assumes to be inhouse (Ollama)
- The AI will write the Splunk config files and validate them in a sandbox against the suppied log samples.
- The AI model must be allowed to search sites lihe <https://splunkbase.splunk.com> for already existing solutions

## 5 Vector Database

- We will use Pinecone as Vector database
- The vector DB should contain Splunk docs From <https://docs.splunk.com/Documentation> related to the Platform
- Previous uploaded sampels
- Previously developed TAs

## Web interface

- Knowledge files can only be uploaded by an admin or knowledge manager of the system, So we need a rolebased access to the web interface.

- It should support PDF and Mardown files with documentation.
- zip or tar.gz files with existing TAs

## 7 Deployment requirements

- The system must be able to run as containers, and it must be possible to specify the location of the ollama implementation Host/IP and port.

- This will most likely be implemented on-prem, possibly in a k8 devops environement
- There must be a logon to the web interface. This must support SAML auth and Oauth, as well as local users for test and development.
- The agent can browse the web, but it must be possible to whitelist or blacklist the sites it can visit.

## 8 Success criteria

In order of impotance

1. Reduce time used to onboard new logs
2. Reduce number of ingestion and field extraction errors in production.

## 9. Open questions

- We know some customers will require guidance on how to provide the requirements.
- It will be ok for the customer to not know which fields needs to be extracted, the system must lean towards extracting fields relevant for the CIM whenever possble.
- We do knot know the sample lengths we will recieve, but resonable limit of 500 MB should be applied.
