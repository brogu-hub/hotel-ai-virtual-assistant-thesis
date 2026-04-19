---
type: paper
status: summarized
year: 2026
authors: [European Union]
venue: "EU Regulation — Official Journal of the European Union"
url: "https://artificialintelligenceact.eu"
key_claim: "AI systems in essential services (travel/housing) are classified under specific risk tiers and require documented risk mitigation and AI System Inventory."
methodology: "Regulatory instrument — enforced from 2026"
contradicts: []
supports:
  - concepts/pii_redaction_and_compliance
tags: [paper, regulation, EU, compliance, AI-Act, legal, risk-tiers]
created: 2026-04-19
updated: 2026-04-19
---

# EU AI Act (2026)

> **Authors**: European Union (European Parliament and Council)
> **Venue / Year**: EU Regulation, enforced 2026
> **Link**: https://artificialintelligenceact.eu

## Key claim

AI systems used in "essential services" — including travel and housing — are classified under specific risk tiers. Organizations deploying such systems must:
1. Maintain an **AI System Inventory**
2. Document risk mitigation measures
3. Not process sensitive personal data (passports, credit cards) through cloud LLM APIs without safeguards

## Methodology

Regulatory instrument with phased enforcement. Applies to any AI system deployed within the EU or affecting EU residents.

## Results / requirements

- **Risk tiers:** High-risk systems in essential services require documentation, testing, and human oversight.
- **PII obligations:** Align with GDPR — sensitive guest data must be protected before reaching LLM APIs.
- **AI System Inventory:** Organizations must catalog all deployed AI systems with risk classifications.

## Relevance to thesis

Provides the regulatory framework justifying PII redaction, Human-in-the-Loop checkpoints, and compliance architecture in the hotel chatbot. The thesis should acknowledge EU AI Act compliance requirements, especially if the system is intended for deployment in EU markets.

## Related

- [[concepts/pii_redaction_and_compliance]]
- [[entities/Microsoft Presidio]]
- [[thesis/evaluation_methodology]]
