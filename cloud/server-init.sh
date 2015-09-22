#!/bin/bash

if [[ ! -d /home/copernicus/.copernicus/_default ]] ; then
  echo "Creating configuration."
  if [[ ${COPERNICUS_PASSWORD} == default ]]; then
    echo "Please set the COPERNICUS_PASSWORD environment variable."
    exit 1
  fi
  cpc-server setup -p ${COPERNICUS_PASSWORD} /home/copernicus/projects
  cpc-server bundle -o /home/copernicus/.copernicus/client.cnx
fi

exec "$@"
