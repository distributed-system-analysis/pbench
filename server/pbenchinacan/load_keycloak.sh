#!/bin/bash -e

# This scripts creates the custom keycloak server image with following configuration
# 1. A realm with the name 'pbench'
# 2. A client 'pbench-server' under the realm pbench
# 3. A user 'admin' under the realm pbench
# 4. An 'ADMIN' role under the client pbench-server
# 5. ADMIN role assigned to the admin user.

# This file uses a realm of 'pbench' and a client name of 'pbench-server'
# unless specified otherwise by the environment variables, because that is
# what the Pbench Server default configuration uses.

# The script defaults to using master realm username/password as admin/admin
# unless specified otherwise by 'ADMIN_USERNAME' and 'ADMIN_PASSWORD' env
# variables. The script also defaults the keycloak redirect URI as
# "http://localhost:8080/*" unless specified otherwise by 'KEYCLOAK_REDIRECT_URI'
# env variable.

KEYCLOAK_BASE_IMAGE=${KEYCLOAK_BASE_IMAGE:-"quay.io/keycloak/keycloak:latest"}
KEYCLOAK_HOST_PORT=${KEYCLOAK_HOST_PORT:-"http://localhost:8090"}
KEYCLOAK_HEALTH_URI="${KEYCLOAK_HOST_PORT}/health"
KEYCLOAK_REDIRECT_URI=${KEYCLOAK_REDIRECT_URI:-"http://localhost:8080/*"}
ADMIN_USERNAME=${ADMIN_USERNAME:-"admin"}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-"admin"}
REALM=${KEYCLOAK_REALM:-"pbench"}
CLIENT=${KEYCLOAK_CLIENT:-"pbench-server"}
KEYCLOAK_IMAGE_TAG=${KEYCLOAK_IMAGE_TAG:-"test3"}

container_name="mykeycloak"
podman run -d --rm --name ${container_name} -p 8090:8090 \
-e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
${KEYCLOAK_BASE_IMAGE} start-dev --health-enabled=true --http-port=8090

end_in_epoch_secs=$(( $(date +"%s") + 120 ))

until curl -s -o /dev/null ${KEYCLOAK_HEALTH_URI}; do
  if [[ $(date +"%s") -ge ${end_in_epoch_secs} ]]; then
    echo "Timed out connecting to Keycloak" >&2
    exit 1
  fi
  echo "Waiting for the Keycloak server" >&2
  sleep 2
done

echo "Keycloak health url is up" >&2

status_code=$(curl -s -o /dev/null -w "%{http_code}" ${KEYCLOAK_HEALTH_URI})

while [[ $(date +"%s") -le ${end_in_epoch_secs} ]]; do
  if [[ "${status_code}" == "200" ]]; then
    keycloak_status=$(curl -s ${KEYCLOAK_HEALTH_URI} | jq -r ".status")
    if [[ ${keycloak_status} == "UP" ]]; then
      echo "Keycloak Server is up" >&2
      break
    else
      echo "Keycloak Server status is not UP" >&2
    fi
  else
    echo "Keycloak health status code ${status_code}" >&2
  fi
  status_code=$(curl -s -o /dev/null -w "%{http_code}" ${KEYCLOAK_HEALTH_URI})
  sleep 2
done

# Run the custom configuration

echo
echo "KEYCLOAK_HOST_PORT: ${KEYCLOAK_HOST_PORT}"

echo
echo "Getting admin access token"
echo "--------------------------"

ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_HOST_PORT}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USERNAME}" \
  -d "password=${ADMIN_PASSWORD}" \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' | jq -r '.access_token')

echo "ADMIN_TOKEN=${ADMIN_TOKEN}"
echo

echo "Creating ${REALM} realm"
echo "--------------"

curl -i -X POST "${KEYCLOAK_HOST_PORT}/admin/realms" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"realm": "'${REALM}'", "enabled": true}'

echo "Creating ${CLIENT} client"
echo "---------------"

CLIENT_CONF=$(curl -si -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
   -d '{"clientId": "'${CLIENT}'", "directAccessGrantsEnabled": true, "serviceAccountsEnabled": true, "redirectUris": ["'${KEYCLOAK_REDIRECT_URI}'"]}')


CLIENT_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${CLIENT_CONF} | sed -e 's|.*/||')
echo "client_id=${CLIENT_ID}"
echo

echo "Getting client secret"
echo "---------------------"

PBENCH_CLIENT_SECRET=$(curl -s -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/client-secret" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.value')

echo "PBENCH_CLIENT_SECRET=${PBENCH_CLIENT_SECRET}"
echo

echo "Creating an 'ADMIN' role under ${CLIENT} client of the ${REALM} realm"
echo "--------------------"

curl -i -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name": "ADMIN"}'

ROLE_ID=$(curl -s "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[0].id')

echo "ROLE_ID=${ROLE_ID}"
echo

echo "Creating an 'admin' user inside ${REALM} realm"
echo "-------------"

USER=$(curl -si -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "enabled": true, "credentials": [{"type": "password", "value": "123", "temporary": false}]}')

USER_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${USER} | sed -e 's|.*/||')
echo "USER_ID=${USER_ID}"
echo

echo "Assigning 'ADMIN' client role to the user 'admin' created above"
echo "---------------------------"

curl -i -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users/${USER_ID}/role-mappings/clients/${CLIENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '[{"id":"'${ROLE_ID}'","name":"ADMIN"}]'

sleep 5

podman pause ${container_name}
podman commit ${container_name} images.paas.redhat.com/pbench/pbenchinacan-keycloak:${KEYCLOAK_IMAGE_TAG}
podman unpause ${container_name}
podman stop ${container_name}

podman push images.paas.redhat.com/pbench/pbenchinacan-keycloak:${KEYCLOAK_IMAGE_TAG}
