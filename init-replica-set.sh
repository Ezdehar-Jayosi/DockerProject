#!/bin/bash

# Commands for MongoDB replica set initialization
mongo --host mongo1 <<EOF
rs.initiate({
 _id: "myReplicaSet",
 members: [
   {_id: 0, host: "mongo1"},
   {_id: 1, host: "mongo2"},
   {_id: 2, host: "mongo3"}
 ]
})
EOF

# Commands for creating the EDS database and ECollection collection
mongo --host mongo1 <<EOF
use EDS
db.createCollection("ECollection")
EOF
