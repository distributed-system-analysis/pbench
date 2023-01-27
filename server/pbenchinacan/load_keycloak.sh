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

KEYCLOAK_HOST_PORT=${KEYCLOAK_HOST_PORT:-"http://localhost:8090"}
KEYCLOAK_REDIRECT_URI=${KEYCLOAK_REDIRECT_URI:-"http://localhost:8080/*"}
ADMIN_USERNAME=${ADMIN_USERNAME:-"admin"}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-"admin"}
REALM=${KEYCLOAK_REALM:-"pbench"}
CLIENT=${KEYCLOAK_CLIENT:-"pbench-server"}

keycloak_health_uri="${KEYCLOAK_HOST_PORT}/health"
end_in_epoch_secs=$(( $(date +%s) + 120 ))

until curl -s -o /dev/null ${keycloak_health_uri}; do
  if [[ $(date +%s) -ge ${end_in_epoch_secs} ]]; then
    echo "Timed out connecting to Keycloak" >&2
    exit 1
  fi
  echo "Waiting for the Keycloak server" >&2
  sleep 2
done

echo "Keycloak health url is up" >&2

while [[ $(date +%s) -le ${end_in_epoch_secs} ]]; do
  status_code=$(curl -s -o /dev/null -w "%{http_code}" ${keycloak_health_uri})
  if [[ "${status_code}" == "200" ]]; then
    keycloak_status=$(curl -s ${keycloak_health_uri} | jq -r ".status")
    if [[ ${keycloak_status} == "UP" ]]; then
      echo "Keycloak Server is up" >&2
      break
    else
      echo "Keycloak Server status is not UP" >&2
    fi
  else
    echo "Keycloak health status code ${status_code}" >&2
  fi
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

# Verify that the user id has a role assigned to it
USER_ROLES=$(curl -s "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users/${USER_ID}/role-mappings/clients/${CLIENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" | jq -r '.[].name')

if [[ ${USER_ROLES} == *"ADMIN"* ]]; then
  echo "The Keycloak configuration is complete."
else
  echo "Could not assign client role the 'admin' user."
  exit 1
fi
