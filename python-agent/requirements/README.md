# Python Dependency Layout

## Agent service

- `runtime.txt`: production/runtime dependencies for `python-agent`
- `dev.txt`: local development and test dependencies for `python-agent`
- `../requirements.txt`: backward-compatible shortcut to `dev.txt`

Install runtime dependencies only:

```bash
pip install -r python-agent/requirements/runtime.txt
```

Install local development dependencies:

```bash
pip install -r python-agent/requirements/dev.txt
```

## Generated backend/fullstack projects

- `generated-backend.txt`: dependency template copied into generated Python backend artifacts

The agent service itself does not install Flask. Those dependencies are emitted into generated projects by `BackendGenerator`.
