#!/bin/bash

# Commands for MongoDB replica set initialization

# Sleep to ensure the replica set is initiated
sleep 5

# Connect to mongo1 and initiate the replica set again
docker exec -i mongo1 mongo --eval "rs.initiate({
 _id: \"myReplicaSet\",
 members: [
   {_id: 0, host: \"mongo1\"},
   {_id: 1, host: \"mongo2\"},
   {_id: 2, host: \"mongo3\"}
 ]})"


echo "Replica set initialization completed."


# Wait for the replica set to be initialized
until docker exec -i mongo1 --eval 'rs.status().ok' | grep -q 1; do
    echo "Waiting for replica set to be initialized..."
    sleep 5
done

# Commands for creating the EDS database and ECollection collection
docker exec -i mongo1 mongo --eval 'use EDS; db.createCollection("ECollection")'

echo "Database and collection creation completed."
