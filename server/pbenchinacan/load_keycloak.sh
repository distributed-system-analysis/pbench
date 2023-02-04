#!/bin/bash -e

# This script configures a running Keycloak server with following configuration
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
# These values must match the options "realm" and "client in the
# "openid-connect" section of the pbench server configuration file.
REALM=${KEYCLOAK_REALM:-"pbench-server"}
CLIENT=${KEYCLOAK_CLIENT:-"pbench-server-client"}

end_in_epoch_secs=$(date --date "2 minutes" +%s)

# Run the custom configuration

ADMIN_TOKEN=""
while true; do
  ADMIN_TOKEN=$(curl -s -f -X POST "${KEYCLOAK_HOST_PORT}/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${ADMIN_USERNAME}" \
    -d "password=${ADMIN_PASSWORD}" \
    -d 'grant_type=password' \
    -d 'client_id=admin-cli' | jq -r '.access_token')
  if [[ -n "${ADMIN_TOKEN}" ]]; then
    break
  elif [[ $(date +%s) -ge ${end_in_epoch_secs} ]]; then
    echo "Timed out connecting to Keycloak" >&2
    exit 1
  else
    echo "Waiting for the Keycloak server" >&2
  fi
  sleep 2
done

echo
echo "Keycloak connection successful on : ${KEYCLOAK_HOST_PORT}"
echo

status_code=$(curl -f -s -o /dev/null -w "%{http_code}" -X POST "${KEYCLOAK_HOST_PORT}/admin/realms" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"realm": "'${REALM}'", "enabled": true}')

if [[ "${status_code}" != "201" ]]; then
  echo "Realm creation failed with ${status_code}"
  exit 1
else
  echo "Created ${REALM} realm"
fi

CLIENT_CONF=$(curl -si -f -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
   -d '{"clientId": "'${CLIENT}'", "directAccessGrantsEnabled": true, "serviceAccountsEnabled": true, "redirectUris": ["'${KEYCLOAK_REDIRECT_URI}'"]}')


CLIENT_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${CLIENT_CONF} | sed -e 's|.*/||')
if [[ -z "${CLIENT_ID}" ]]; then
  echo "${CLIENT} id is empty"
  exit 1
else
  echo "Created ${CLIENT} client"
fi

PBENCH_CLIENT_SECRET=$(curl -s -f -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/client-secret" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.value')

if [[ -z "${PBENCH_CLIENT_SECRET}" ]]; then
  echo "${CLIENT} secret is empty"
  exit 1
fi

status_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name": "ADMIN"}')

if [[ "${status_code}" != "201" ]]; then
  echo "ADMIN role creation failed with ${status_code}"
  exit 1
else
  echo "Created an 'ADMIN' role under ${CLIENT} client of the ${REALM} realm"
fi

ROLE_ID=$(curl -s -f "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/clients/${CLIENT_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[0].id')

if [[ -z "${ROLE_ID}" ]]; then
  echo "ADMIN role id is empty"
  exit 1
fi

USER=$(curl -si -f -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "enabled": true, "credentials": [{"type": "password", "value": "123", "temporary": false}]}')

USER_ID=$(grep -o -e 'http://[^[:space:]]*' <<< ${USER} | sed -e 's|.*/||')

if [[ -z "${USER_ID}" ]]; then
  echo "User id is empty"
  exit 1
else
  echo "Created an 'admin' user inside ${REALM} realm"
fi

status_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${KEYCLOAK_HOST_PORT}/admin/realms/${REALM}/users/${USER_ID}/role-mappings/clients/${CLIENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '[{"id":"'${ROLE_ID}'","name":"ADMIN"}]')

if [[ "${status_code}" != "204" ]]; then
  echo "Assigning 'ADMIN' client role to the user 'admin' failed with ${status_code}"
  exit 1
else
  echo "Assigned an 'ADMIN' client role to the user 'admin' created above"
fi

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
