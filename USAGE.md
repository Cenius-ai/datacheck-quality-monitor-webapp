# Using datacheck-quality-monitor

## Overview

An open-source Plotly Dash dashboard for dataset validation rules, rule history and failing-row samples.

## Quickstart

After completing the install steps in `INSTALL.md`:

```bash
flask --app app run --debug    # start the server
# in another terminal:
curl http://localhost:8000/health
```

## Endpoints

Every endpoint below was extracted from the source by the route scanner (Next.js / FastAPI / Flask / Django / Express).

| Method | Path | Source file |
|--------|------|-------------|
| `GET` | `/health` | `datacheck/main.py` |
| `GET` | `/login` | `datacheck/main.py` |
| `POST` | `/signout` | `datacheck/main.py` |

### curl examples

#### `GET /health`

```bash
curl http://localhost:8000/health
```

#### `GET /login`

```bash
curl http://localhost:8000/login
```

#### `POST /signout`

```bash
curl -X POST http://localhost:8000/signout \
     -H 'Content-Type: application/json' \
     -d '{"field": "value"}'
```

## Worked example

1. Boot the server (`flask --app app run --debug`).
2. Hit a smoke-test endpoint:

```bash
curl -sS http://localhost:8000/health
```

3. If you get a JSON / HTML response, the server is healthy. Inspect `.env` if it errors with an auth/config failure.

## Reference

### Entry points

_No explicit entry points declared in this project's manifests._

### Surface index (auto-extracted)

| Kind | Title | Source file |
|------|-------|-------------|
| route | `GET /health` | `datacheck/main.py` |
| route | `GET /login` | `datacheck/main.py` |
| route | `POST /signout` | `datacheck/main.py` |

## Next steps

- Read [INSTALL.md](./INSTALL.md) if anything in the Quickstart didn't work.
- Inspect `.env.example` for the full list of environment variables this project understands.
- See [README.md](./README.md) for the architecture diagram + feature list.
