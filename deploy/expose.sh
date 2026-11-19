docker run --rm --name stma-db-viewer \
  --network "$(docker inspect "$(docker compose --env-file .env.docker ps -q db)" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}')" \
  -p 127.0.0.1:5433:5433 \
  alpine/socat TCP-LISTEN:5433,fork,reuseaddr TCP:db:5432
