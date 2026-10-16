# Trinetra services

The supported local stack is defined in `infra/docker-compose.yml`. From this
directory, run:

```bash
docker compose -f infra/docker-compose.yml up --build
```

The UI is available at http://localhost:3000. Service documentation is at
ports 8001 (explanations), 8002 (model), 8003 (automation), and 8004
(monitoring), under `/docs`.
