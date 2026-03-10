# Positioning and Strategic Analysis

## Category Definition

**AI Execution Governance**

The control plane between AI intent and real-world execution.

### Alternative Category Names Considered

1. **AI Execution Governance** (selected)
2. Autonomous Control Plane
3. Agent Execution Firewall
4. AI Action Verification Infrastructure
5. Autonomous Risk Infrastructure

**AI Execution Governance** was selected because it:
- Implies a systematic, infrastructure-level approach (not a tool or plugin)
- Uses "governance" which resonates with enterprise security, compliance, and risk teams
- Positions the project alongside established categories (data governance, API governance, cloud governance)
- Avoids "firewall" (too narrow) and "verification" (too passive)

### Single-Line Positioning

> The control plane between AI intent and real-world execution.

### Problem Framing

AI agents are being deployed into production environments with the ability to execute consequential actions: database operations, financial transactions, infrastructure changes, API calls. These agents operate with varying levels of autonomy, across multiple frameworks, in environments where a single misclassified action can cause irreversible damage.

No governance layer exists between what an agent decides and what it does. Observability tools detect problems after execution. Permission systems apply binary allow/deny without risk gradients. Neither approach addresses the fundamental requirement: evaluate every action before execution, assess its risk in context, simulate its consequences, and produce auditable evidence of every decision.

### Threat Framing

The threat is not theoretical. Production databases have been deleted by coding agents despite freeze instructions. Recursive loops have burned tens of thousands of dollars running unnoticed for days. Malicious tool packages have been distributed through agent skill registries. These incidents are accelerating as agent deployment scales.

The window for building governance infrastructure is closing. As agents become more autonomous and more widely deployed, the cost of incidents will grow and the expectations of regulators, customers, and insurers will formalize. Organizations that deploy agents without execution governance will face the same reckoning that organizations without data governance faced a decade ago.

### Why This Must Exist

1. **Agents act, they don't just respond.** Unlike chatbots, agents execute real-world actions with real-world consequences. Governance must happen at the execution boundary, not the conversation boundary.

2. **Risk is contextual and continuous.** The same tool call can be safe or catastrophic depending on arguments, environment, history, and timing. Binary permission models cannot capture this.

3. **Audit trails must be cryptographic.** When an agent causes a $2.3M loss, "we logged it" is not sufficient. Tamper-proof, chain-hashed, independently verifiable records are the baseline.

4. **Governance must be framework-agnostic.** Agents are built on OpenAI, Anthropic, LangChain, CrewAI, AutoGen, MCP, and custom frameworks. Governance cannot be locked to any single provider.

5. **The regulatory landscape is forming.** The EU AI Act, SOC 2, ISO 27001, and emerging AI-specific standards will require evidence of execution governance. The infrastructure must exist before the mandates arrive.

---

## Acquisition and Strategic Interest

### Why AI Labs Would Care

- **Liability reduction** -- execution governance reduces the risk surface of agent deployments built on their models
- **Enterprise enablement** -- governance infrastructure is a prerequisite for enterprise adoption of autonomous agents
- **Differentiation** -- offering built-in governance makes a platform more attractive to regulated industries
- **Standards influence** -- owning the governance layer shapes how the industry defines "safe agent execution"

### Why Security Companies Would Care

- **New market category** -- AI execution governance is an emerging category with no dominant player
- **Existing customer base** -- enterprise security customers deploying agents need governance immediately
- **Compliance tooling** -- passport and ledger infrastructure maps directly to SOC 2, ISO 27001, EU AI Act requirements
- **Detection + prevention** -- unlike traditional security (detect and respond), Preflight prevents before execution

### Why Observability Platforms Would Care

- **Pre-execution signals** -- Preflight generates rich telemetry (risk scores, simulation results, drift metrics) that complement post-execution observability
- **Pipeline integration** -- Prometheus metrics, OpenTelemetry spans, and structured logging integrate with existing observability stacks
- **Agent monitoring gap** -- current observability tools were not designed for autonomous agent workloads; Preflight fills that gap
- **Data moat** -- the liability ledger and passport chain create a unique data asset for understanding agent behavior at scale

### Attractive Metrics

- Number of actions governed per day
- Mean risk scores across deployments
- Number of blocked high-risk actions (near-misses)
- Framework coverage (number of supported agent frameworks)
- Passport volume and ledger size
- Enterprise tenant count
- Policy rule count across deployments

---

## Brutal Audit

### Current Weaknesses

1. **No production deployments cited.** The README references incidents but not production use cases. Design partners and early adopters would add credibility.

2. **No benchmarks from real workloads.** Performance numbers exist but are not tied to specific hardware or methodology documentation.

3. **No community yet.** No Discord, no forum, no public discussions. A project this technical needs a community of practitioners.

4. **Trust kernel naming.** The `trust_kernel/` directory name is unconventional. Consider aligning with the "governance" vocabulary.

5. **Demo is functional but not polished.** The demo backend and frontend exist but need deployment instructions, a hosted version, and a clear 2-minute demo script.

6. **No social proof.** No logos, no testimonials, no "used by" section. Even placeholder design partner slots would help.

7. **Spec is defined but not widely referenced.** The Action Passport v1.0 spec exists but is not positioned as a community standard.

### Overengineering Risks

- Monte Carlo simulation adds latency for actions where risk scoring alone is sufficient. Consider making it opt-in rather than threshold-triggered.
- Mirror World sandbox execution is conceptually strong but adds complexity. Ensure it has a clear bypass for environments where sandboxing is not feasible.
- M-of-N consensus is enterprise-grade but may be premature for initial adoption. Keep it as an opt-in module.

### Missing Adoption Hooks

- No hosted playground (try Preflight in-browser)
- No "time to first verdict" metric (how fast can a new user see Preflight working)
- No GitHub Action that can be added to any repo in 2 minutes
- No Slack/Discord community for questions and feedback

### Missing Developer Experience

- No `preflight init` command that scaffolds configuration
- No interactive CLI walkthrough for first-time users
- Error messages should include actionable next steps
- Need more examples: "How do I add a custom policy?", "How do I add a new integration?"

### Missing Social Proof

- No design partner logos or placeholder slots
- No "in production at" section
- No conference talks or blog posts referenced
- No academic citations or research references

---

## 30-Day Transformation Plan

### Week 1: Foundation

- [ ] Finalize README, ARCHITECTURE.md, SECURITY.md, THREAT_MODEL.md
- [ ] Finalize CONTRIBUTING.md and CODE_OF_CONDUCT.md
- [ ] Polish demo application with deployment instructions
- [ ] Set up GitHub Issues templates (bug, feature, security)
- [ ] Create GitHub Discussions board
- [ ] Run full test suite, ensure 90%+ coverage

### Week 2: Adoption Hooks

- [ ] Create `preflight init` CLI command
- [ ] Build hosted demo at demo.preflight.dev (or equivalent)
- [ ] Write "Getting Started in 5 Minutes" tutorial
- [ ] Create GitHub Action for any-repo integration
- [ ] Add 3-5 complete example scripts with different frameworks
- [ ] Record 2-minute demo video

### Week 3: Community and Positioning

- [ ] Launch Discord or GitHub Discussions
- [ ] Write "Why Preflight Exists" blog post
- [ ] Open Design Partner Program applications
- [ ] Submit to relevant newsletters (AI safety, dev tools)
- [ ] Create Twitter/X presence with technical content
- [ ] Reach out to 10 AI agent teams for feedback

### Week 4: Polish and Launch

- [ ] Complete whitepaper first draft
- [ ] Performance benchmark documentation with methodology
- [ ] Dependency audit and security review
- [ ] Package and publish to PyPI
- [ ] Launch post on Hacker News, Reddit r/MachineLearning
- [ ] Submit to Product Hunt (if appropriate for the audience)
