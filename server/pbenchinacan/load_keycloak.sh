#!/bin/bash -e

# This scripts loads the keycloak server with following configuration
# 1. A realm with the name pbench
# 2. A client 'pbench-server' under the realm pbench
# 3. A user test_user
# 4. An ADMIN role under the client pbench-client
# 5. ADMIN role assigned to the test_user user.

# At the moment the Pbench-server requires a Keycloak server with at least
# a realm and a client configuration specified above.
# This script assumes that Keycloak server is running and the master realm
# username/password are admin/admin

KEYCLOAK_HOST_PORT=${KEYCLOAK_HOST_PORT:-"localhost:8090"}
KEYCLOAK_REDIRECT_URI=${KEYCLOAK_REDIRECT_URI:-"http://localhost:8080/*"}
ADMIN_USERNAME=${ADMIN_USERNAME:-"admin"}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-"admin"}
REALM=${KEYCLOAK_REALM:-"pbench"}
CLIENT=${KEYCLOAK_CLIENT:-"pbench-server"}

echo
echo "KEYCLOAK_HOST_PORT: ${KEYCLOAK_HOST_PORT}"

echo
echo "Getting admin access token"
echo "--------------------------"

ADMIN_TOKEN=$(curl -s -X POST "http://${KEYCLOAK_HOST_PORT}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USERNAME}" \
  -d "password=${ADMIN_PASSWORD}" \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' | jq -r '.access_token')

echo "ADMIN_TOKEN=${ADMIN_TOKEN}"
echo

echo "Creating realm"
echo "--------------"

curl -i -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"realm": "'${REALM}'", "enabled": true}'

echo "Creating client"
echo "---------------"

CLIENT_CONF=$(curl -si -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
   -d '{"clientId": "'${CLIENT}'", "directAccessGrantsEnabled": true, "serviceAccountsEnabled": true, "redirectUris": ["'${KEYCLOAK_REDIRECT_URI}'"]}')


CLIENT_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${CLIENT_CONF} | sed -e 's|.*/||')
echo "client_id=${CLIENT_ID}"
echo

echo "Getting client secret"
echo "---------------------"

PBENCH_CLIENT_SECRET=$(curl -s -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/client-secret" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.value')

echo "PBENCH_CLIENT_SECRET=${PBENCH_CLIENT_SECRET}"
echo

echo "Creating an 'ADMIN' role under ${CLIENT} client of the ${REALM} realm"
echo "--------------------"

curl -i -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name": "ADMIN"}'

ROLE_ID=$(curl -s "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[0].id')

echo "ROLE_ID=${ROLE_ID}"
echo

echo "Creating a user inside ${REALM} realm"
echo "-------------"

USER=$(curl -si -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "enabled": true, "credentials": [{"type": "password", "value": "123", "temporary": false}]}')

USER_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${USER} | sed -e 's|.*/||')
echo "USER_ID=${USER_ID}"
echo

echo "Setting ${CLIENT} client role to the user created above"
echo "---------------------------"

curl -i -X POST "http://${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users/${USER_ID}/role-mappings/clients/${CLIENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '[{"id":"'${ROLE_ID}'","name":"ADMIN"}]'
