# Delete all data
curl -X DELETE "http://localhost:8000/api/projects/00000000-0000-0000-0000-000000000000"

# Seed a small graph
docker compose exec backend ogi dev seed --name "Small Scale-Free" --nodes 100 --edges 300 --topology scale-free
docker compose exec backend ogi dev seed --name "Small Clustered" --nodes 100 --edges 300 --topology clustered

# Seed a medium graph
docker compose exec backend ogi dev seed --name "Medium Scale-Free" --nodes 1000 --edges 3000 --topology scale-free
docker compose exec backend ogi dev seed --name "Medium Clustered" --nodes 1000 --edges 3000 --topology clustered

# Seed a large graph
docker compose exec backend ogi dev seed --name "Large Scale-Free" --nodes 10000 --edges 30000 --topology scale-free
docker compose exec backend ogi dev seed --name "Large Clustered" --nodes 10000 --edges 30000 --topology clustered

# Run benchmarks on existing projects
docker compose exec backend ogi dev benchmark --project-name "Small Scale-Free"
docker compose exec backend ogi dev benchmark --project-name "Medium Scale-Free"
docker compose exec backend ogi dev benchmark --project-name "Large Scale-Free"

docker compose exec backend ogi dev benchmark --project-name "Small Clustered"
docker compose exec backend ogi dev benchmark --project-name "Medium Clustered"
docker compose exec backend ogi dev benchmark --project-name "Large Clustered"
