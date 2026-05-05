# Pluginized Agent Extensions

## Goal

This directory hosts explicitly allowlisted `*_agent.py` plugins.

Current scope:

- `reviewer` plugins
- `generator` plugins for scaffold-style project output
- `tester` plugins for test command strategy selection

## Required files

- `*_agent.py`: plugin implementation
- `*_agent.manifest.json`: plugin metadata and permissions

## Safety model

- Plugins are instantiated from local manifests, but can execute only when allowed by policy
- Policy supports `global_allow`, `environment_allow`, and `project_allow`
- Default behavior is deny-by-default
- Plugin entrypoint must stay inside `python-agent/plugins/` and target `*_agent.py`
- Permissions are enforced by selection policy before execution
- Default capability policy blocks `sandbox_exec` and `network_access`
- Plugin runtime uses circuit breaker protection keyed by `plugin_id`
- Default breaker policy: `failure_threshold=3`, `recovery_timeout_seconds=30`
- When breaker is `open`, plugin execution is skipped and the built-in implementation is used
- Fallback remains the built-in agent implementation
