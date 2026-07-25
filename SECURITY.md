# Security

## Credential Handling

- API keys are loaded from environment variables only (ANTHROPIC_API_KEY)
- No credentials are stored in source code, configuration files, or state
- No credentials are written to logs, telemetry, or artifacts
- Credentials are not requested until the specific integration phase requires them

## Code Execution

- AI-generated and imported strategy code must not execute unrestricted on the host
- The system enforces sandboxing boundaries for generated code
- AI/imported strategies require human approval before promotion

## Real-Money Trading

- Real-money trading is explicitly disabled in project_config.json (real_money_trading: false)
- The system will refuse any operation that could enable real-money trading
- Paper trading and simulation are separate, controlled features

## Human Approval Required For

- Credential input or storage
- Irreversible destructive actions
- Activation of paid services
- Licensing or legal decisions
- Consequential architecture changes
- Anything that could enable real-money trading

## Data Safety

- Core platform data is kept local by default
- PostgreSQL is the local primary system of record
- No data is transmitted to external services without explicit configuration
- Dataset mutations are tracked and versioned
- Completed experiment datasets are never silently mutated

## Agent Safety

- Agents operate within bounded retry limits (default: 3 retries per task)
- Remediation cycles are bounded (default: 2 cycles max)
- Concurrent agent execution is capped at 2 (semaphore-enforced)
- Resource limits prevent the system from consuming the entire machine
- ReviewerAgent independently validates all claims and evidence integrity

## Telemetry Safety

- Telemetry never fabricates data
- Every metric is classified: MEASURED, DERIVED, ESTIMATED, or UNAVAILABLE
- Failures are recorded, never hidden
- Human interventions are explicitly tracked with reasons
